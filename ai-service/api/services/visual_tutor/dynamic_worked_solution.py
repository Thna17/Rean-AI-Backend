"""Universal dynamic worked-solution builder for ReanAI visual tutor.

Provides step-by-step whiteboard solutions for ANY in-scope STEM problem:
1. Employs SymPy for deterministic mathematical ground truth when available.
2. Uses DeepSeek / LLM with RAG curriculum grounding when no deterministic solver exists.
3. Formats all solutions into deterministic board actions (WRITE_TEXT, WRITE_EQUATION, SHOW_TABLE)
   so that Flutter's whiteboard displays step-by-step animations without double-writes.
4. Marks solutions as Verified (Tier 1) or AI-Generated Unverified (Tier 2).
5. Supports interactive follow-up Q&A by appending replies below the completed board.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional

import sympy

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorScreenState,
    VisualTutorSpeech,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.chemistry_stoichiometry import (
    match_chemistry_stoichiometry_problem,
    solve_stoichiometry,
    WorkedChemistrySolution,
)
from api.services.visual_tutor.physics_kinematics import (
    match_physics_kinematics_problem,
    solve_kinematics,
    WorkedPhysicsSolution,
)
from api.services.curriculum.curriculum_store import get_default_curriculum_store
from api.services.visual_tutor.rag_curriculum_gate import ClassificationResult
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan
from api.services.visual_tutor.worked_solution import (
    match_worked_solution,
    solve_limit,
    WorkedSolution,
)

logger = logging.getLogger(__name__)


@dataclass
class GenericSolutionStep:
    key: str
    heading: str
    explanation: str
    latex: Optional[str] = None
    table: Optional[dict[str, Any]] = None


@dataclass
class GenericWorkedSolution:
    problem_text: str
    steps: list[GenericSolutionStep]
    answer_text: str
    answer_latex: str
    is_verified: bool
    curriculum_topic: Optional[str] = None
    curriculum_sources: list[str] = field(default_factory=list)


# In-memory cache for dynamic solutions and session follow-up tracking
_dynamic_solution_cache: dict[str, GenericWorkedSolution] = {}
_dynamic_followup_cache: dict[str, str] = {}
_session_followups: dict[str, list[GenericSolutionStep]] = {}


def _detect_khmer_request(question: str, request: VisualTutorTurnRequest) -> bool:
    """Detect if the student is asking in Khmer or explicitly requesting a Khmer explanation."""
    if re.search(r"[\u1780-\u17ff]", question):
        return True
    if re.search(r"\b(?:khmer|cambodian|in\s+khmer|to\s+khmer|as\s+khmer|ខ្មែរ)\b", question, re.IGNORECASE):
        return True
    lang_mode = getattr(request.language_mode, "value", request.language_mode) or ""
    if "khmer" in str(lang_mode).lower():
        return True
    return False


def _identify_referenced_step(
    question: str,
    solution: GenericWorkedSolution,
    previous_replies: list[GenericSolutionStep],
) -> tuple[Optional[GenericSolutionStep], Optional[int]]:
    """Identify which step of the solution the student is asking about using semantic keywords and history."""
    q_lower = question.lower()
    total_steps = len(solution.steps)
    if total_steps == 0:
        return None, None

    # 1. Step number mentions (English & Khmer)
    step_num_match = re.search(r"\bstep\s*([1-9]|10)\b", q_lower)
    if step_num_match:
        idx = int(step_num_match.group(1)) - 1
        if 0 <= idx < total_steps:
            return solution.steps[idx], idx

    km_num_map = {
        "១": 0, "1": 0, "មួយ": 0,
        "២": 1, "2": 1, "ពីរ": 1,
        "៣": 2, "3": 2, "បី": 2,
        "៤": 3, "4": 3, "បួន": 3,
    }
    for km_digit, idx in km_num_map.items():
        if f"ជំហានទី{km_digit}" in q_lower or f"ជំហានទី {km_digit}" in q_lower or f"ជំហាន {km_digit}" in q_lower:
            if idx < total_steps:
                return solution.steps[idx], idx

    # Ordinals
    if re.search(r"\b(?:first\s+step|1st\s+step|beginning|initial|start)\b", q_lower) or "ជំហានដំបូង" in question or "ជំហានទីមួយ" in question:
        return solution.steps[0], 0
    if re.search(r"\b(?:second\s+step|2nd\s+step)\b", q_lower):
        if total_steps > 1:
            return solution.steps[1], 1
    if re.search(r"\b(?:third\s+step|3rd\s+step)\b", q_lower):
        if total_steps > 2:
            return solution.steps[2], 2
    if re.search(r"\b(?:last\s+step|final\s+step)\b", q_lower) or "ជំហានចុងក្រោយ" in question:
        return solution.steps[-1], total_steps - 1

    # 2. Mathematical token & content semantic matching
    # E.g. square root / sqrt / \sqrt
    if any(term in q_lower for term in ("square root", "sqrt", "root", "ឫស")):
        for idx, s in enumerate(solution.steps):
            if any(term in (s.latex or "").lower() for term in (r"\sqrt", "sqrt")):
                return s, idx
            if any(term in s.explanation.lower() for term in ("square root", "sqrt", "root", "ឫស")):
                return s, idx

    # Match tokens against step latex and explanation
    q_tokens = set(re.findall(r"[a-zA-Z_]\w*|[\u1780-\u17ff]+", q_lower))
    stopwords = {
        "why", "how", "what", "did", "we", "do", "take", "is", "the", "a", "an",
        "in", "to", "of", "can", "you", "explain", "about", "this", "that", "mean",
        "means", "get", "got", "where", "from", "for", "it",
        "តើ", "ហេតុអ្វី", "ដូចម្តេច", "យ៉ាងណា", "ពន្យល់", "បាន", "ជា",
    }
    informative_tokens = q_tokens - stopwords

    best_step = None
    best_idx = None
    best_score = 0.0

    for idx, s in enumerate(solution.steps):
        score = 0.0
        s_text = f"{s.heading} {s.explanation} {s.latex or ''}".lower()
        for token in informative_tokens:
            if len(token) > 1 and token in s_text:
                score += 2.0
            elif len(token) == 1 and re.search(r"\b" + re.escape(token) + r"\b", s_text):
                score += 2.0
        if s.latex:
            for token in informative_tokens:
                if len(token) >= 2 and token in s.latex.lower():
                    score += 3.0
                elif len(token) == 1 and re.search(r"\b" + re.escape(token) + r"\b", s.latex.lower()):
                    score += 3.0
        if score > best_score:
            best_score = score
            best_step = s
            best_idx = idx

    if best_score >= 2.0:
        return best_step, best_idx

    # If question refers to prior conversation and previous_replies exist
    if previous_replies and any(term in q_lower for term in ("that", "it", "more", "again", "ទៀត")):
        return solution.steps[-1], total_steps - 1

    return None, None


def _to_khmer_numeral(n: int) -> str:
    """Convert integer to Khmer numeral string."""
    km_digits = {"0": "០", "1": "១", "2": "២", "3": "៣", "4": "៤", "5": "៥", "6": "៦", "7": "៧", "8": "៨", "9": "៩"}
    return "".join(km_digits.get(d, d) for d in str(n))


def _find_targeted_misconception(
    question: str,
    chunks: list[CurriculumChunk],
) -> Optional[str]:
    """Find matching misconception from curriculum chunks to provide pedagogical remediation."""
    norm_q = re.sub(r"([a-zA-Z])_(\d+)", r"\1\2", question.lower())
    q_tokens = set(re.findall(r"\w+", norm_q))
    for chunk in chunks:
        for misc in getattr(chunk, "common_misconceptions", []):
            mistake = ""
            correction = ""
            if isinstance(misc, dict):
                mistake = misc.get("mistake") or misc.get("text") or ""
                correction = misc.get("correction") or ""
            elif hasattr(misc, "text") or hasattr(misc, "mistake"):
                mistake = getattr(misc, "text", "") or getattr(misc, "mistake", "")
                correction = getattr(misc, "correction", "")
            elif isinstance(misc, str):
                mistake = misc
                correction = ""
            if not mistake and not correction:
                continue

            norm_m = re.sub(r"([a-zA-Z])_(\d+)", r"\1\2", mistake.lower())
            mistake_tokens = set(re.findall(r"\w+", norm_m))
            overlap = mistake_tokens & q_tokens - {"the", "is", "a", "an", "in", "to", "of", "and", "what", "does"}
            if len(overlap) >= 2 or (len(overlap) == 1 and any(len(t) >= 2 for t in overlap)):
                return f"Common student misconception: '{mistake}'. Pedagogical remediation: {correction}"
    return None


def _extract_khmer_terms_summary(chunks: list[CurriculumChunk]) -> str:
    """Extract glossary of authoritative Khmer curriculum terms."""
    terms: dict[str, str] = {}
    for chunk in chunks:
        if chunk.khmer_terms:
            terms.update(chunk.khmer_terms)
    if not terms:
        return ""
    items = [f"{en}: {km}" for en, km in list(terms.items())[:6]]
    return "Khmer Curriculum Terms: " + ", ".join(items)


def build_dynamic_worked_solution_turn(
    request: VisualTutorTurnRequest,
    classification: ClassificationResult,
    *,
    session_id: str,
    llm_client: Any = None,
) -> VisualTutorTurnResponse:
    """Solve any STEM problem and return a complete step-by-step whiteboard turn."""
    is_khmer = classification.is_khmer or _uses_khmer(request)

    # Reset accumulated session followups for a new problem
    session_key = session_id or (request.message or request.current_state.problem_text or "default").strip()
    _session_followups.pop(session_key, None)
    _session_followups.pop(session_id, None)

    # 1. Attempt deterministic solver first
    deterministic_solution = _try_solve_deterministic(request, classification)
    if deterministic_solution is not None:
        return _build_turn_response(
            request,
            deterministic_solution,
            session_id=session_id,
            is_khmer=is_khmer,
            board_update_mode="replace",
        )

    # 2. Dynamic RAG-grounded LLM solution
    problem_text = (request.message or request.current_state.problem_text or "").strip()
    cache_key = f"{problem_text}:{is_khmer}:{classification.is_verified}"
    if cache_key in _dynamic_solution_cache:
        solution = _dynamic_solution_cache[cache_key]
    else:
        solution = _solve_with_llm_rag(
            problem_text=problem_text,
            classification=classification,
            is_khmer=is_khmer,
            llm_client=llm_client,
        )
        _dynamic_solution_cache[cache_key] = solution

    return _build_turn_response(
        request,
        solution,
        session_id=session_id,
        is_khmer=is_khmer,
        board_update_mode="replace",
    )


def answer_dynamic_followup(
    request: VisualTutorTurnRequest,
    classification: ClassificationResult,
    *,
    session_id: str,
    llm_client: Any = None,
) -> VisualTutorTurnResponse:
    """Answer a student's follow-up question while keeping the whiteboard solution visible."""
    question = (request.message or "").strip()
    is_khmer = classification.is_khmer or _detect_khmer_request(question, request)
    problem_text = (request.current_state.problem_text or "").strip()

    # Reconstruct the base solution
    cache_key = f"{problem_text}:{is_khmer}:{classification.is_verified}"
    solution = _dynamic_solution_cache.get(cache_key)
    if solution is None:
        for alt_lang in (True, False):
            alt_key = f"{problem_text}:{alt_lang}:{classification.is_verified}"
            if alt_key in _dynamic_solution_cache:
                solution = _dynamic_solution_cache[alt_key]
                break
    if solution is None:
        deterministic = _try_solve_deterministic(request, classification)
        if deterministic is not None:
            solution = deterministic
        else:
            solution = _solve_with_llm_rag(
                problem_text=problem_text,
                classification=classification,
                is_khmer=False,
                llm_client=llm_client,
            )
            _dynamic_solution_cache[cache_key] = solution

    # Retrieve accumulated session followups to preserve across consecutive turns
    session_key = session_id or problem_text or "default"
    previous_replies = list(_session_followups.get(session_key, []))

    # Reconcile if client sent rendered_board_actions with earlier follow-up replies
    rendered = request.metadata.get("rendered_board_actions") or []
    for action in rendered:
        if isinstance(action, dict) and str(action.get("id", "")).startswith("ws-followup-reply-"):
            text = action.get("text", "")
            if text and not any(r.explanation in text for r in previous_replies):
                previous_replies.append(
                    GenericSolutionStep(
                        key=f"prev_{len(previous_replies)}",
                        heading=f"Explanation {len(previous_replies) + 1}",
                        explanation=text,
                    )
                )

    reply_idx = len(previous_replies)

    # 1. Identify which step the student is asking about
    target_step, target_idx = _identify_referenced_step(question, solution, previous_replies)

    # 2. Query curriculum chunk's common_misconceptions and khmer_terms
    chunks = list(classification.matching_chunks)
    if not chunks:
        try:
            store = get_default_curriculum_store()
            scored = store.search_chunks_by_query(
                problem_text,
                grade=classification.grade,
                subject=classification.subject if classification.subject in ("mathematics", "physics", "chemistry") else None,
                limit=3,
            )
            chunks = [c for _, c in scored]
        except Exception as err:
            logger.debug("Curriculum query error in followup: %s", err)

    targeted_misconception = _find_targeted_misconception(question, chunks)
    khmer_terms_str = _extract_khmer_terms_summary(chunks)

    # 3. Generate explanation with language switching & LaTeX preservation
    q_cache_key = f"{problem_text}:{question}:{is_khmer}:{target_idx}"
    if q_cache_key in _dynamic_followup_cache:
        explanation = _dynamic_followup_cache[q_cache_key]
    else:
        explanation = _generate_followup_reply(
            question=question,
            solution=solution,
            target_step=target_step,
            target_idx=target_idx,
            targeted_misconception=targeted_misconception,
            khmer_terms_str=khmer_terms_str,
            is_khmer=is_khmer,
            llm_client=llm_client,
        )
        _dynamic_followup_cache[q_cache_key] = explanation

    if is_khmer:
        step_km = _to_khmer_numeral(target_idx + 1) if target_idx is not None else ""
        reply_km = _to_khmer_numeral(reply_idx + 1)
        reply_heading = f"ការពន្យល់ជំហានទី {step_km}" if target_idx is not None else f"ការពន្យល់បន្ថែម {reply_km}"
    else:
        reply_heading = f"Explanation of Step {target_idx + 1}" if target_idx is not None else f"Additional Explanation {reply_idx + 1}"

    reply_step = GenericSolutionStep(
        key=f"followup_{reply_idx}",
        heading=reply_heading,
        explanation=explanation,
    )
    previous_replies.append(reply_step)
    _session_followups[session_key] = previous_replies

    # 4. Append to whiteboard with board_update_mode: "append" and monotonic board_version
    return _build_turn_response(
        request,
        solution,
        session_id=session_id,
        is_khmer=is_khmer,
        extra_sections=previous_replies,
        message_override=explanation,
        board_update_mode="append",
    )


def _try_solve_deterministic(
    request: VisualTutorTurnRequest,
    classification: ClassificationResult,
) -> Optional[GenericWorkedSolution]:
    """Check if SymPy deterministic solvers can handle this problem."""
    msg = request.message or request.current_state.problem_text or ""

    # Math limit
    limit_problem = match_worked_solution(request)
    if limit_problem is not None:
        try:
            ws = solve_limit(limit_problem)
            steps = [
                GenericSolutionStep(
                    key=s.key,
                    heading=s.heading,
                    explanation=s.explanation,
                    latex=s.latex,
                    table=s.table,
                )
                for s in ws.steps
            ]
            return GenericWorkedSolution(
                problem_text=msg,
                steps=steps,
                answer_text=ws.answer_text,
                answer_latex=ws.answer_latex,
                is_verified=True,
                curriculum_topic="Limits of Functions",
                curriculum_sources=["sympy_limits_v1"],
            )
        except Exception:
            logger.warning("Deterministic limit solve failed; falling back to dynamic RAG")

    # Physics kinematics
    physics_problem = match_physics_kinematics_problem(request)
    if physics_problem is not None:
        try:
            ps = solve_kinematics(physics_problem)
            steps = [
                GenericSolutionStep(
                    key=s.key,
                    heading=s.heading,
                    explanation=s.explanation,
                    latex=s.latex,
                    table=s.table,
                )
                for s in ps.steps
            ]
            return GenericWorkedSolution(
                problem_text=msg,
                steps=steps,
                answer_text=ps.answer_text,
                answer_latex=ps.answer_latex,
                is_verified=True,
                curriculum_topic="1D Kinematics",
                curriculum_sources=["sympy_kinematics_v1"],
            )
        except Exception:
            logger.warning("Deterministic physics solve failed; falling back to dynamic RAG")

    # Chemistry stoichiometry
    chemistry_problem = match_chemistry_stoichiometry_problem(request)
    if chemistry_problem is not None:
        try:
            cs = solve_stoichiometry(chemistry_problem)
            steps = [
                GenericSolutionStep(
                    key=s.key,
                    heading=s.heading,
                    explanation=s.explanation,
                    latex=s.latex,
                    table=s.table,
                )
                for s in cs.steps
            ]
            return GenericWorkedSolution(
                problem_text=msg,
                steps=steps,
                answer_text=cs.answer_text,
                answer_latex=cs.answer_latex,
                is_verified=True,
                curriculum_topic="Stoichiometry",
                curriculum_sources=["sympy_chemistry_v1"],
            )
        except Exception:
            logger.warning("Deterministic chemistry solve failed; falling back to dynamic RAG")

    return None


DYNAMIC_WORKED_SOLUTION_SYSTEM_PROMPT = (
    "You are ReanAI, an expert visual whiteboard tutor for Cambodian high school students (Grade 10–12).\n"
    "Solve the STEM problem step-by-step for display on a digital whiteboard.\n"
    "Output strict JSON only with this schema:\n"
    '{"steps":[{"key":"step1","heading":"Step 1 · ...","explanation":"...","latex":"...","table":{"columns":["..."],"rows":[["..."]]}}],'
    '"answer_text":"...","answer_latex":"..."}\n'
    "Rules:\n"
    "1. Provide 2 to 4 clear logical steps with concise pedagogical explanations.\n"
    "2. Write clean LaTeX equations for 'latex' and 'answer_latex' without outer dollar signs ($).\n"
    "3. When presenting tabular data (such as chemistry stoichiometry ICE tables, data tables, or truth tables), include 'table' with 'columns' and 'rows'. Otherwise omit 'table'.\n"
    "4. Align strictly with curriculum formulas and steps when provided.\n"
    "5. Return JSON only without markdown formatting or code fences."
)

DYNAMIC_FOLLOWUP_SYSTEM_PROMPT = (
    "You are ReanAI, an encouraging high school STEM visual whiteboard tutor.\n"
    "Explain the whiteboard step clearly and concisely in 2-3 sentences.\n"
    "Address the student's question directly with educational encouragement.\n"
    "Use standard LaTeX for mathematical expressions."
)


def _normalize_table(tbl: Any) -> Optional[dict[str, Any]]:
    """Validate and normalize table dictionary for VisualTutorTableSpec and TeachingPlanTable."""
    if not isinstance(tbl, dict):
        return None
    cols = tbl.get("columns") or tbl.get("headers") or []
    rows = tbl.get("rows") or []
    if not isinstance(cols, list) or not isinstance(rows, list):
        return None
    cols_clean = [str(c).strip() for c in cols if str(c).strip()]
    if not (1 <= len(cols_clean) <= 6):
        return None
    rows_clean = []
    for r in rows[:10]:
        if not isinstance(r, list):
            continue
        row_cells = [str(cell).strip() for cell in r]
        if len(row_cells) < len(cols_clean):
            row_cells.extend([""] * (len(cols_clean) - len(row_cells)))
        elif len(row_cells) > len(cols_clean):
            row_cells = row_cells[: len(cols_clean)]
        rows_clean.append(row_cells)
    if not (1 <= len(rows_clean) <= 10):
        return None
    return {
        "columns": cols_clean,
        "rows": rows_clean,
    }


def _solve_with_llm_rag(
    problem_text: str,
    classification: ClassificationResult,
    is_khmer: bool,
    llm_client: Any,
) -> GenericWorkedSolution:
    """Solve problem using LLM grounded with curriculum knowledge from RAG."""
    # Top-3 most relevant curriculum chunks: start with classification
    chunks = list(classification.matching_chunks[:3])
    if classification.is_verified and len(chunks) < 3:
        try:
            store = get_default_curriculum_store()
            scored = store.search_chunks_by_query(
                problem_text,
                grade=classification.grade,
                subject=classification.subject if classification.subject in ("mathematics", "physics", "chemistry") else None,
                limit=3,
            )
            existing_ids = {c.id for c in chunks}
            for score, chunk in scored:
                if chunk.id not in existing_ids and len(chunks) < 3:
                    chunks.append(chunk)
                    existing_ids.add(chunk.id)
        except Exception as err:
            logger.debug("CurriculumStore dynamic query fallback error: %s", err)

    is_verified = classification.is_verified
    topic = classification.topic or (chunks[0].topic if chunks else "General STEM Problem")
    chunk_ids = [c.id for c in chunks]

    curriculum_context_lines = []
    for chunk in chunks:
        parts = [f"Topic: {chunk.topic}"]
        if chunk.subtopic:
            parts.append(f"Subtopic: {chunk.subtopic}")
        if chunk.formulas:
            exprs = []
            for f in chunk.formulas[:3]:
                if isinstance(f, str):
                    exprs.append(f)
                elif hasattr(f, "expression"):
                    exprs.append(f.expression)
                elif isinstance(f, dict):
                    exprs.append(f.get("expression", ""))
            exprs = [e for e in exprs if e]
            if exprs:
                parts.append(f"Formulas: {', '.join(exprs)}")
        if chunk.solution_steps:
            steps_text = []
            for s in chunk.solution_steps[:4]:
                if isinstance(s, str):
                    steps_text.append(s)
                elif hasattr(s, "heading"):
                    steps_text.append(f"{s.heading}: {getattr(s, 'explanation', '')}")
                elif isinstance(s, dict):
                    steps_text.append(f"{s.get('heading', '')}: {s.get('explanation', '')}")
            if steps_text:
                parts.append(f"Solution Blueprint: {' -> '.join(steps_text)}")
        if chunk.khmer_terms:
            terms_str = ", ".join(f"{en}={km}" for en, km in list(chunk.khmer_terms.items())[:5])
            parts.append(f"Khmer Terms: {terms_str}")
        if getattr(chunk, "common_misconceptions", None):
            misc = chunk.common_misconceptions[:2]
            misc_strs = []
            for m in misc:
                if isinstance(m, str):
                    misc_strs.append(m)
                elif hasattr(m, "mistake"):
                    misc_strs.append(f"Avoid: {m.mistake}")
                elif isinstance(m, dict):
                    misc_strs.append(f"Avoid: {m.get('mistake', '')}")
            if misc_strs:
                parts.append(f"Misconceptions: {'; '.join(misc_strs)}")
        curriculum_context_lines.append(" | ".join(parts))

    grounding_str = "; ".join(curriculum_context_lines) if curriculum_context_lines else "Standard high-school curriculum."
    lang_str = "Khmer (headings and explanations in Khmer, math in LaTeX)" if is_khmer else "English"
    user_prompt = f"Curriculum: {grounding_str}\nLanguage: {lang_str}\nProblem: {problem_text}"

    try:
        raw_output = None
        if llm_client is not None and hasattr(llm_client, "complete"):
            raw_output = llm_client.complete(
                system_prompt=DYNAMIC_WORKED_SOLUTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        if not raw_output:
            from api.services.visual_tutor.llm_teaching_planner import DeepSeekVisualTutorLLMClient
            client = DeepSeekVisualTutorLLMClient()
            raw_output = client.complete(
                system_prompt=DYNAMIC_WORKED_SOLUTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

        parsed = _parse_llm_solution_json(raw_output)
        if parsed is not None:
            steps = [
                GenericSolutionStep(
                    key=s.get("key", f"step_{idx + 1}"),
                    heading=s.get("heading", f"Step {idx + 1}"),
                    explanation=s.get("explanation", ""),
                    latex=s.get("latex"),
                    table=_normalize_table(s.get("table")),
                )
                for idx, s in enumerate(parsed.get("steps", []))
            ]
            return GenericWorkedSolution(
                problem_text=problem_text,
                steps=steps,
                answer_text=parsed.get("answer_text", "Solution complete"),
                answer_latex=parsed.get("answer_latex", ""),
                is_verified=is_verified,
                curriculum_topic=topic,
                curriculum_sources=chunk_ids,
            )
    except Exception as exc:
        logger.warning("LLM dynamic solve failed (%s); building graceful fallback solution", exc)

    # Graceful fallback solution
    return _build_fallback_solution(
        problem_text,
        is_khmer,
        classification,
        topic=topic,
        chunk_ids=chunk_ids,
        is_verified=is_verified,
    )


def _parse_llm_solution_json(raw: str) -> Optional[dict[str, Any]]:
    """Clean and parse LLM JSON response."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "steps" in data:
            return data
    except Exception:
        pass
    try:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "steps" in data:
                return data
    except Exception:
        pass
    return None


def _build_fallback_solution(
    problem_text: str,
    is_khmer: bool,
    classification: ClassificationResult,
    *,
    topic: Optional[str] = None,
    chunk_ids: Optional[list[str]] = None,
    is_verified: Optional[bool] = None,
) -> GenericWorkedSolution:
    """Graceful structured fallback when LLM is offline or timed out."""
    h1 = "ជំហានទី ១ · កំណត់លំហាត់" if is_khmer else "Step 1 · Identify Problem"
    e1 = (
        f"លំហាត់៖ {problem_text}។ យើងកំណត់ទិន្នន័យ និងរូបមន្តដែលត្រូវប្រើ។"
        if is_khmer
        else f"Problem: {problem_text}. Identify given parameters and necessary principles."
    )
    h2 = "ជំហានទី ២ · ដំណោះស្រាយជាជំហាន" if is_khmer else "Step 2 · Step-by-Step Working"
    e2 = (
        "អនុវត្តរូបមន្ត និងគណនាតាមលំដាប់លំដោយ។"
        if is_khmer
        else "Apply mathematical relations and evaluate step-by-step."
    )
    ans = "ដំណោះស្រាយបានបញ្ចប់" if is_khmer else "Solution completed"

    steps = [
        GenericSolutionStep(key="identify", heading=h1, explanation=e1),
        GenericSolutionStep(key="solve", heading=h2, explanation=e2),
    ]
    resolved_verified = classification.is_verified if is_verified is None else is_verified
    resolved_topic = topic or classification.topic or "General STEM Problem"
    resolved_sources = chunk_ids if chunk_ids is not None else [c.id for c in classification.matching_chunks]
    return GenericWorkedSolution(
        problem_text=problem_text,
        steps=steps,
        answer_text=ans,
        answer_latex=r"\text{Solution}",
        is_verified=resolved_verified,
        curriculum_topic=resolved_topic,
        curriculum_sources=resolved_sources,
    )


def _generate_followup_reply(
    question: str,
    solution: GenericWorkedSolution,
    *,
    target_step: Optional[GenericSolutionStep] = None,
    target_idx: Optional[int] = None,
    targeted_misconception: Optional[str] = None,
    khmer_terms_str: Optional[str] = None,
    is_khmer: bool = False,
    llm_client: Any = None,
) -> str:
    """Generate concise conversational reply to student follow-up question with pedagogical remediation."""
    steps_summary = " | ".join(f"{s.heading}: {s.explanation}" for s in solution.steps[:4])
    target_step_str = (
        f"Target Step: {target_step.heading} - {target_step.explanation} (LaTeX: {target_step.latex or 'none'})"
        if target_step
        else "Target Step: Overall Solution"
    )
    lang_instruction = (
        "Respond in fluent natural Khmer. Keep mathematical variables and formulas strictly in standard LaTeX (e.g. $n_1$, $\\sqrt{39}$, $PV = nRT$)."
        if is_khmer
        else "Respond in clear, encouraging English. Use standard LaTeX for mathematical expressions."
    )

    prompt_lines = [
        f"Language Instruction: {lang_instruction}",
        f"Problem: {solution.problem_text}",
        f"Full Solution Steps: {steps_summary}",
        f"{target_step_str}",
    ]
    if targeted_misconception:
        prompt_lines.append(f"Pedagogical Remediation: {targeted_misconception}")
    if khmer_terms_str:
        prompt_lines.append(f"Authoritative Terminology: {khmer_terms_str}")
    prompt_lines.append(f"Student Question: {question}")

    user_prompt = "\n".join(prompt_lines)

    try:
        if llm_client is not None and hasattr(llm_client, "complete"):
            return llm_client.complete(
                system_prompt=DYNAMIC_FOLLOWUP_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        from api.services.visual_tutor.llm_teaching_planner import DeepSeekVisualTutorLLMClient
        client = DeepSeekVisualTutorLLMClient()
        return client.complete(
            system_prompt=DYNAMIC_FOLLOWUP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except Exception as exc:
        logger.warning("Follow-up generation failed: %s", exc)
        if is_khmer:
            if target_step:
                return (
                    f"ជំហាននេះ ({target_step.heading}) អនុវត្តតាមរូបមន្តស្តង់ដារ និងទ្រឹស្តីបទនៃមុខវិជ្ជា។ "
                    f"{target_step.latex or ''} ត្រូវបានប្រើដើម្បីគណនាតម្លៃពិតប្រាកដ។"
                )
            return "ជំហាននេះអនុវត្តតាមរូបមន្តស្តង់ដារនៃមុខវិជ្ជា។ អ្នកអាចសួរបន្ថែមអំពីជំហានជាក់លាក់ណាមួយបាន!"
        else:
            if target_step:
                return (
                    f"This step ({target_step.heading}) applies the core principle and formula {target_step.latex or ''} "
                    "to evaluate the exact result."
                )
            return "This step follows standard curriculum principles. Feel free to ask about any specific step!"


def _build_turn_response(
    request: VisualTutorTurnRequest,
    solution: GenericWorkedSolution,
    *,
    session_id: str,
    is_khmer: bool,
    extra_sections: Optional[list[GenericSolutionStep]] = None,
    message_override: Optional[str] = None,
    board_update_mode: str = "replace",
) -> VisualTutorTurnResponse:
    """Build standardized VisualTutorTurnResponse with deterministic board actions."""
    turn_id = str(uuid.uuid4())
    actions: list[VisualTutorBoardAction] = []
    plan_actions: list[dict[str, Any]] = []

    def add(action_type: VisualTutorCanvasActionType, section: str, action_id_override: Optional[str] = None, **fields: Any) -> None:
        index = len(actions)
        action_id = action_id_override or f"ws-{section}-{index}"
        zone = fields.pop("layout_zone", "working")
        table_val = fields.pop("table", None)
        duration = fields.pop("duration_ms", 450)
        action_kwargs = dict(fields)
        if table_val is not None:
            action_kwargs["table"] = table_val
        actions.append(
            VisualTutorBoardAction(
                id=action_id,
                type=action_type,
                sequence_index=index,
                duration_ms=duration,
                layout_zone=zone,
                layout_flow="vertical",
                section_id=section,
                **action_kwargs,
            )
        )
        item: dict[str, Any] = {
            "id": action_id,
            "type": action_type.value,
            "sequence_index": index,
            "duration_ms": duration,
            "layout_zone": zone,
            "layout_flow": "vertical",
            "section_id": section,
        }
        for key in ("text", "latex", "requires_student_response", "task_type"):
            if key in fields and fields[key] is not None:
                item[key] = fields[key]
        if table_val is not None:
            item["table"] = table_val
        plan_actions.append(item)

    # Add steps
    for step in solution.steps:
        section = f"step-{step.key}"
        add(
            VisualTutorCanvasActionType.WRITE_TEXT,
            section,
            text=f"{step.heading}. {step.explanation}",
        )
        if step.latex:
            add(
                VisualTutorCanvasActionType.WRITE_EQUATION,
                section,
                latex=step.latex,
                duration_ms=550,
            )
        if step.table:
            norm_tbl = _normalize_table(step.table)
            if norm_tbl:
                add(
                    VisualTutorCanvasActionType.SHOW_TABLE,
                    section,
                    table=norm_tbl,
                    duration_ms=700,
                    width=420,
                    height=40 + 28 * len(norm_tbl.get("rows", [])),
                )

    # Add Final Answer
    answer_label = "ចម្លើយ" if is_khmer else "Answer"
    add(
        VisualTutorCanvasActionType.WRITE_TEXT,
        "answer",
        text=f"{answer_label} · {solution.answer_text}",
    )
    if solution.answer_latex:
        add(
            VisualTutorCanvasActionType.WRITE_EQUATION,
            "answer",
            latex=solution.answer_latex,
            duration_ms=600,
        )

    # Add extra reply sections (for follow-up questions) with ws-followup-reply-<idx>
    for reply_idx, reply in enumerate(extra_sections or []):
        add(
            VisualTutorCanvasActionType.WRITE_TEXT,
            f"followup-reply-{reply_idx}",
            action_id_override=f"ws-followup-reply-{reply_idx}",
            text=f"{reply.heading}. {reply.explanation}",
        )
        if reply.latex:
            add(
                VisualTutorCanvasActionType.WRITE_EQUATION,
                f"followup-reply-latex-{reply_idx}",
                action_id_override=f"ws-followup-reply-latex-{reply_idx}",
                latex=reply.latex,
                duration_ms=500,
            )

    # Add student task
    task_text = (
        "សួរខ្ញុំអំពីជំហានណាមួយ ឬសាកល្បងលំហាត់ថ្មីមួយទៀត។"
        if is_khmer
        else "Ask me about any step you'd like explained, or try another problem."
    )
    add(
        VisualTutorCanvasActionType.STUDENT_TASK,
        "next",
        layout_zone="student_task",
        text=task_text,
        requires_student_response=True,
        task_type="conceptual_operation",
        duration_ms=0,
    )

    tutor_message = message_override or (
        f"នេះជាដំណោះស្រាយលម្អិតមួយជំហានម្តងៗ។ {solution.answer_text}"
        if is_khmer
        else f"Here is the full worked solution, step by step. {solution.answer_text}"
    )

    incoming_ver = (
        request.client_board_version
        or request.metadata.get("client_board_version")
        or request.metadata.get("board_version")
        or getattr(request.current_state, "board_version", None)
        or 1
    )
    base_ver = incoming_ver if board_update_mode == "append" else 0
    next_ver = incoming_ver + 1 if board_update_mode == "append" else 1

    # Prepare metadata with 3-tier verification and board update mode
    metadata: dict[str, Any] = {
        "worked_solution": True,
        "verified": solution.is_verified,
        "curriculum_status": "verified_curriculum" if solution.is_verified else "ai_unverified",
        "curriculum_topic": solution.curriculum_topic,
        "curriculum_sources": solution.curriculum_sources,
        "source": "dynamic_worked_solution",
        "board_update_mode": board_update_mode,
        "is_followup": (board_update_mode == "append"),
        "board_version": next_ver,
        "base_board_version": base_ver,
    }

    teaching_plan = validate_teaching_plan(
        {
            "schema_version": 1,
            "representation": "worked_example",
            "learning_objective": (
                "យល់គ្រប់ជំហានក្នុងការដោះស្រាយ"
                if is_khmer
                else "Understand every step of this solution."
            ),
            "teaching_message": tutor_message,
            "board_actions": plan_actions,
            "allowed_student_actions": ["submit_answer", "explain_differently", "request_hint"],
            "hidden_answer_policy": {
                "mode": "reveal_allowed",
                "deterministic_policy_permits_final_reveal": True,
            },
            "next_state_policy": {
                "correct": "continue",
                "invalid": "reteach",
                "incomplete": "ask_for_work",
                "stuck": "reteach",
                "hint": "continue",
                "explain_differently": "reteach",
            },
        }
    ).model_dump(mode="json")

    board = VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title=solution.problem_text or "Whiteboard Solution",
        items=[
            VisualTutorBoardItem(
                label=step.heading,
                content=step.latex or step.explanation,
                status="completed",
            )
            for step in solution.steps
        ],
        metadata=metadata,
    )

    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=turn_id,
        screen_state=VisualTutorScreenState.ASKING_QUESTION,
        tutor_status="Waiting for you",
        spoken_text=tutor_message,
        display_text=tutor_message,
        teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
        final_answer_locked=False,
        student_task=task_text,
        board=board,
        board_actions=actions,
        board_version=next_ver,
        base_board_version=base_ver,
        allowed_actions=[
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
        ],
        quick_actions=[VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY],
        mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
        metadata={
            **metadata,
            "teaching_plan": teaching_plan,
        },
    )


def _uses_khmer(request: VisualTutorTurnRequest) -> bool:
    """Check if the student uses Khmer language."""
    text = f"{request.message or ''} {request.current_state.problem_text or ''}"
    if re.search(r"[\u1780-\u17ff]", text):
        return True
    lang_mode = getattr(request.language_mode, "value", request.language_mode) or ""
    return "khmer" in str(lang_mode).lower()
