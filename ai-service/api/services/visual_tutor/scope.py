"""Unified curriculum scope definitions and enforcement for Visual Tutor.

This module is the single source of truth for Visual Tutor curriculum boundaries:
- Grade: Grade 12 only.
- Subjects: Mathematics, Physics, Chemistry.
- Languages: English, Khmer, Bilingual.

Used by:
- api/services/visual_tutor/orchestrator.py (scope lock and turn dispatch)
- api/services/visual_tutor/pilot.py (supervised pilot gate)
- client lesson catalog alignment
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Set

from api.services.visual_tutor.solvers import parse_limit_of_function

SUPPORTED_GRADES: Set[int] = {12}

SUBJECT_MATH = "mathematics"
SUBJECT_PHYSICS = "physics"
SUBJECT_CHEMISTRY = "chemistry"

SUPPORTED_SUBJECTS: Set[str] = {
    SUBJECT_MATH,
    SUBJECT_PHYSICS,
    SUBJECT_CHEMISTRY,
}

SUBJECT_ALIASES: dict[str, str] = {
    "mathematics": SUBJECT_MATH,
    "math": SUBJECT_MATH,
    "maths": SUBJECT_MATH,
    "គណិតវិទ្យា": SUBJECT_MATH,
    "physics": SUBJECT_PHYSICS,
    "រូបវិទ្យា": SUBJECT_PHYSICS,
    "chemistry": SUBJECT_CHEMISTRY,
    "គីមីវិទ្យា": SUBJECT_CHEMISTRY,
}

UNSUPPORTED_SUBJECT_ALIASES: dict[str, str] = {
    "biology": "biology",
    "ជីវវិទ្យា": "biology",
    "english": "english",
    "english language": "english",
    "ភាសាអង់គ្លេស": "english",
    "khmer": "khmer",
    "khmer language": "khmer",
    "ភាសាខ្មែរ": "khmer",
    "history": "history",
    "ប្រវត្តិវិទ្យា": "history",
    "geography": "geography",
    "ភូមិវិទ្យា": "geography",
    "morality": "morality",
    "សីលធម៌": "morality",
}

SUPPORTED_LANGUAGE_MODES: Set[str] = {"english", "khmer", "bilingual", "en", "km"}

# Topics with verified, deterministic solvers ready today
TOPICS_WITH_VERIFIED_SOLVER: Set[str] = {
    "limits of functions",
    "limits",
    "math-g12-limits-of-functions",
    "math.g12.lesson1.limits-of-functions",
}

_KHMER_RE = re.compile(r"[\u1780-\u17ff]")
_BIOLOGY_RE = re.compile(
    r"\b(biology|photosynthesis|mitosis|meiosis|dna|rna|genetics|cell|cells|organism|ecosystem|species|chloroplast|enzyme)\b",
    re.IGNORECASE,
)
_BIOLOGY_KM_RE = re.compile(r"(ជីវវិទ្យា|កោសិកា|រស្មីសំយោគ|ហ្សែន|អង់ស៊ីម)")
_PHYSICS_RE = re.compile(
    r"\b(physics|velocity|acceleration|force|gravity|kinematics|momentum|mass|projectile|motion|friction|energy|joules?|m/s|m/s\^2)\b",
    re.IGNORECASE,
)
_PHYSICS_KM_RE = re.compile(r"(រូបវិទ្យា|ល្បឿន|សំទុះ|កម្លាំង|ចលនា|ថាមពល|ទំនាញ|ម៉ាស)")
_CHEMISTRY_RE = re.compile(
    r"\b(chemistry|reaction|chemical|mole|moles|molar|stoichiometry|acid|acids|base|bases|ph|molecule|molecules|atom|atoms|h2o|co2|nacl|o2|h2)\b",
    re.IGNORECASE,
)
_CHEMISTRY_KM_RE = re.compile(r"(គីមីវិទ្យា|ប្រតិកម្ម|សមីការគីមី|ម៉ូល|អាស៊ីត|បាស|អាតូម|ម៉ូលេគុល)")


@dataclass(frozen=True)
class ScopeDecision:
    is_in_scope: bool
    grade: Optional[int]
    subject: str
    topic: Optional[str]
    has_verified_solver: bool
    refusal_reason: Optional[str] = None


def normalize_grade(grade_raw: Any) -> Optional[int]:
    """Parse grade into integer if possible."""
    if grade_raw is None:
        return None
    try:
        if isinstance(grade_raw, int):
            return grade_raw
        text = str(grade_raw).strip().lower()
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else None
    except Exception:
        return None


def normalize_subject(
    subject_raw: Optional[str],
    message: str = "",
    problem_text: str = "",
) -> str:
    """Normalize subject to canonical name or infer from text."""
    combined_text = f"{message} {problem_text}".strip()
    norm = (subject_raw or "").strip().lower()

    if norm in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[norm]
    if norm in UNSUPPORTED_SUBJECT_ALIASES:
        return UNSUPPORTED_SUBJECT_ALIASES[norm]

    # Keyword check for explicit subjects in message
    if _BIOLOGY_RE.search(combined_text) or _BIOLOGY_KM_RE.search(combined_text):
        return "biology"
    if _PHYSICS_RE.search(combined_text) or _PHYSICS_KM_RE.search(combined_text):
        return SUBJECT_PHYSICS
    if _CHEMISTRY_RE.search(combined_text) or _CHEMISTRY_KM_RE.search(combined_text):
        return SUBJECT_CHEMISTRY

    # Check for limits / mathematics
    if parse_limit_of_function(message) is not None or parse_limit_of_function(problem_text) is not None:
        return SUBJECT_MATH

    if norm in {"general", ""}:
        return "general"
    return norm


def check_scope(
    *,
    grade: Optional[int],
    subject: str,
    topic: Optional[str] = None,
    topic_id: Optional[str] = None,
    message: str = "",
    problem_text: str = "",
    language_mode: Optional[str] = None,
) -> ScopeDecision:
    """Evaluate whether a request falls within the allowed Grade 12 STEM scope."""
    norm_grade = normalize_grade(grade)
    norm_subject = normalize_subject(subject, message=message, problem_text=problem_text)
    norm_topic = (topic or "").strip().lower()
    norm_topic_id = (topic_id or "").strip().lower()

    # 1. Check Grade
    # If grade is specified and not 12, it is strictly out of scope
    if norm_grade is not None and norm_grade != 12:
        return ScopeDecision(
            is_in_scope=False,
            grade=norm_grade,
            subject=norm_subject,
            topic=topic,
            has_verified_solver=False,
            refusal_reason="unsupported_grade",
        )

    # 2. Check Subject
    if norm_subject in UNSUPPORTED_SUBJECT_ALIASES.values():
        return ScopeDecision(
            is_in_scope=False,
            grade=norm_grade or 12,
            subject=norm_subject,
            topic=topic,
            has_verified_solver=False,
            refusal_reason="unsupported_subject",
        )

    # If subject is general or undetermined, try limits check
    if norm_subject == "general":
        if parse_limit_of_function(message) is not None or parse_limit_of_function(problem_text) is not None:
            norm_subject = SUBJECT_MATH
        elif _PHYSICS_RE.search(message) or _PHYSICS_KM_RE.search(message):
            norm_subject = SUBJECT_PHYSICS
        elif _CHEMISTRY_RE.search(message) or _CHEMISTRY_KM_RE.search(message):
            norm_subject = SUBJECT_CHEMISTRY

    if norm_subject not in SUPPORTED_SUBJECTS:
        return ScopeDecision(
            is_in_scope=False,
            grade=norm_grade or 12,
            subject=norm_subject,
            topic=topic,
            has_verified_solver=False,
            refusal_reason="unsupported_subject",
        )

    # 3. Check Language Mode if specified
    if language_mode:
        norm_lang = str(language_mode).strip().lower()
        if norm_lang not in SUPPORTED_LANGUAGE_MODES:
            return ScopeDecision(
                is_in_scope=False,
                grade=norm_grade or 12,
                subject=norm_subject,
                topic=topic,
                has_verified_solver=False,
                refusal_reason="unsupported_language",
            )

    # In scope! Determine whether a verified solver is available
    has_solver = False
    if norm_subject == SUBJECT_MATH:
        if norm_topic in TOPICS_WITH_VERIFIED_SOLVER or norm_topic_id in TOPICS_WITH_VERIFIED_SOLVER:
            has_solver = True
        elif parse_limit_of_function(message) is not None or parse_limit_of_function(problem_text) is not None:
            has_solver = True

    return ScopeDecision(
        is_in_scope=True,
        grade=norm_grade or 12,
        subject=norm_subject,
        topic=topic,
        has_verified_solver=has_solver,
    )


def build_out_of_scope_message(language_mode: str = "english") -> dict[str, str]:
    """Generate helpful bilingual out-of-scope refusal text explaining supported curriculum."""
    norm_lang = (language_mode or "english").strip().lower()
    is_khmer = norm_lang in {"khmer", "km"}

    text_en = (
        "This tutor is currently available only for Grade 12 Mathematics, "
        "Physics, and Chemistry. Other grades and subjects are not available yet."
    )
    text_km = (
        "គ្រូបង្រៀននេះបច្ចុប្បន្នគាំទ្រតែថ្នាក់ទី១២ សម្រាប់មុខវិជ្ជា គណិតវិទ្យា "
        "រូបវិទ្យា និងគីមីវិទ្យាប៉ុណ្ណោះ។ កម្រិតថ្នាក់ និងមុខវិជ្ជាផ្សេងទៀតមិនទាន់មាននៅឡើយទេ។"
    )

    if is_khmer:
        message = f"{text_km}\n\n{text_en}"
        student_task = "សូមសាកល្បងលំហាត់ថ្នាក់ទី១២ លើមុខវិជ្ជា គណិតវិទ្យា រូបវិទ្យា ឬគីមីវិទ្យា។"
        board_title = "មិនស្ថិតក្នុងវិសាលភាព (Out of Scope)"
        board_content = text_km
    else:
        message = f"{text_en}\n\n{text_km}"
        student_task = "Try a Grade 12 problem in Mathematics, Physics, or Chemistry."
        board_title = "Not in current scope"
        board_content = text_en

    return {
        "spoken_text": message,
        "display_text": message,
        "student_task": student_task,
        "board_title": board_title,
        "board_content": board_content,
    }


def build_solver_not_ready_message(
    subject: str,
    topic: Optional[str] = None,
    language_mode: str = "english",
) -> dict[str, str]:
    """Generate honest 'solver not ready yet' text for in-scope topics without verified solvers."""
    norm_lang = (language_mode or "english").strip().lower()
    is_khmer = norm_lang in {"khmer", "km"}

    subj_display_en = subject.capitalize() if subject else "STEM"
    subj_km_map = {
        SUBJECT_MATH: "គណិតវិទ្យា",
        SUBJECT_PHYSICS: "រូបវិទ្យា",
        SUBJECT_CHEMISTRY: "គីមីវិទ្យា",
    }
    subj_display_km = subj_km_map.get(subject.lower(), subj_display_en)

    topic_suffix_en = f" ({topic})" if topic else ""
    topic_suffix_km = f" ({topic})" if topic else ""

    text_en = (
        f"The verified solver for Grade 12 {subj_display_en}{topic_suffix_en} is not ready yet. "
        "Currently, full step-by-step solutions are available for Grade 12 Limits of Functions. "
        "Solvers for Physics and Chemistry are under development."
    )
    text_km = (
        f"ប្រព័ន្ធដោះស្រាយសម្រាប់មុខវិជ្ជា {subj_display_km}{topic_suffix_km} ថ្នាក់ទី១២ មិនទាន់រួចរាល់នៅឡើយទេ។ "
        "បច្ចុប្បន្ន ដំណោះស្រាយលម្អិតមួយជំហានម្តងៗមានសម្រាប់តែលីមីតនៃអនុគមន៍ថ្នាក់ទី១២ ហើយប្រព័ន្ធដោះស្រាយសម្រាប់រូបវិទ្យា "
        "និងគីមីវិទ្យាកំពុងស្ថិតក្រោមការអភិវឌ្ឍ។"
    )

    if is_khmer:
        message = f"{text_km}\n\n{text_en}"
        student_task = "សូមសាកល្បងលំហាត់លីមីតនៃអនុគមន៍ថ្នាក់ទី១២ ខណៈពេលដែលប្រព័ន្ធដោះស្រាយនេះកំពុងត្រូវបានបង្កើត។"
        board_title = f"ប្រព័ន្ធដោះស្រាយ {subj_display_km} មិនទាន់រួចរាល់ (Coming Soon)"
        board_content = text_km
    else:
        message = f"{text_en}\n\n{text_km}"
        student_task = "Try a Grade 12 Limits of Functions problem while we build this solver."
        board_title = f"{subj_display_en} Solver Under Development"
        board_content = text_en

    return {
        "spoken_text": message,
        "display_text": message,
        "student_task": student_task,
        "board_title": board_title,
        "board_content": board_content,
    }
