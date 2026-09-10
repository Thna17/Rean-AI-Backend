"""Durable, privacy-safe learner memory for Visual Tutor.

This store records only observable learning evidence.  It deliberately does
not retain model chain-of-thought, hidden answer data, or raw audio/image
content.  A profile is always addressed by the authenticated gateway user and
one normalized subject/topic pair.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest, VisualTutorTurnResponse


MAX_EVIDENCE = 24
MAX_HISTORY = 16
MAX_SUMMARIES = 12
MAX_BOARD_HISTORY = 12
MAX_CONCEPTS = 32


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _topic_key(value: str | None) -> str:
    return " ".join((value or "general").strip().lower().split())[:160] or "general"


def _bounded_unique(values: list[str], value: str | None, limit: int) -> list[str]:
    text = str(value or "").strip()
    result = [item for item in values if item]
    if text:
        result = [item for item in result if item != text]
        result.append(text)
    return result[-limit:]


class LearnerMemoryProfile(BaseModel):
    """Server-only evidence profile.  It must never be returned as tutor UI."""

    user_id: str
    subject: str = "Mathematics"
    topic: str = "General"
    topic_key: str = "general"
    verified_successful_steps: list[dict[str, Any]] = Field(default_factory=list)
    verified_unsuccessful_steps: list[dict[str, Any]] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    hint_levels_used: list[int] = Field(default_factory=list)
    stuck_events: int = 0
    representations_used: list[str] = Field(default_factory=list)
    preferred_successful_representations: list[str] = Field(default_factory=list)
    explanation_strategies_used: list[str] = Field(default_factory=list)
    mastery_evidence: dict[str, Any] = Field(default_factory=dict)
    # Concept keys carry durable counts only; never answer text or model
    # reasoning. Topic remains an index for retrieval, concepts drive mastery.
    concept_mastery: dict[str, dict[str, Any]] = Field(default_factory=dict)
    confidence_evidence: dict[str, float] = Field(default_factory=dict)
    recorded_turn_ids: list[str] = Field(default_factory=list)
    preferred_language: str = "en"
    recent_session_summaries: list[dict[str, Any]] = Field(default_factory=list)
    # These are deliberately structural only. They allow a resumed topic to
    # continue the learner's work without storing answer text or hidden facts.
    active_task: dict[str, str] = Field(default_factory=dict)
    recent_board_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None

    def orchestrator_context(self) -> dict[str, Any]:
        """Compact, non-sensitive facts the deterministic planner may use."""
        evidence = self.mastery_evidence or {}
        return {
            "verified_success_count": int(evidence.get("verified_success_count") or 0),
            "verified_unsuccess_count": int(evidence.get("verified_unsuccess_count") or 0),
            "verified_attempt_count": int(evidence.get("verified_attempt_count") or 0),
            "verified_success_rate": evidence.get("verified_success_rate"),
            "readiness": evidence.get("readiness"),
            "misconceptions": self.misconceptions[-3:],
            "hint_level": self.hint_levels_used[-1] if self.hint_levels_used else 0,
            "stuck_events": self.stuck_events,
            "representations_used": self.representations_used[-8:],
            "preferred_successful_representations": self.preferred_successful_representations[-4:],
            "explanation_strategies_used": self.explanation_strategies_used[-8:],
            "preferred_language": self.preferred_language,
            "active_task_type": self.active_task.get("task_type"),
            "recent_board_representations": [
                str(item["representation"])
                for item in self.recent_board_history[-6:]
                if isinstance(item, dict) and item.get("representation")
            ],
            }


def _verification(response: VisualTutorTurnResponse) -> dict[str, Any]:
    value = response.metadata.get("verification")
    return dict(value) if isinstance(value, dict) else {}


def _evidence_entry(response: VisualTutorTurnResponse, *, status: str) -> dict[str, Any]:
    verification = _verification(response)
    # Store only a bounded, student-independent summary; no raw answer text.
    return {
        "turn_id": response.turn_id,
        "status": status,
        "reason": str(verification.get("reason") or verification.get("reason_code") or "")[:160],
        "timestamp": _now(),
    }


def _representation(response: VisualTutorTurnResponse) -> str | None:
    plan = response.metadata.get("teaching_plan")
    if isinstance(plan, dict) and isinstance(plan.get("representation"), str):
        return plan["representation"]
    decision = response.metadata.get("adaptive_tutor_decision")
    if isinstance(decision, dict) and isinstance(decision.get("representation"), str):
        return decision["representation"]
    value = response.metadata.get("representation")
    return value if isinstance(value, str) else None


def _concept_key(response: VisualTutorTurnResponse, request: VisualTutorTurnRequest) -> str:
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    summary = metadata.get("learner_model_summary")
    explicit = (
        (summary.get("selected_concept") if isinstance(summary, dict) else None)
        or metadata.get("selected_concept")
        or metadata.get("concept")
    )
    if isinstance(explicit, str) and explicit.strip():
        return _topic_key(explicit)
    understanding = metadata.get("problem_understanding")
    if isinstance(understanding, dict) and understanding.get("problem_type"):
        return _topic_key(str(understanding["problem_type"]))
    return _topic_key(request.topic or "general")


def _confidence_band(*, attempts: int, success_rate: float | None) -> str:
    if attempts < 2 or success_rate is None:
        return "emerging"
    if success_rate >= .8:
        return "confident"
    if success_rate >= .5:
        return "developing"
    return "needs_support"


def build_learner_memory_update(
    *,
    previous: LearnerMemoryProfile | dict[str, Any] | None,
    response: VisualTutorTurnResponse,
    request: VisualTutorTurnRequest,
    topic: str | None = None,
    session_summary: dict[str, Any] | None = None,
) -> LearnerMemoryProfile:
    """Return the next profile from deterministic verification evidence only."""
    if isinstance(previous, LearnerMemoryProfile):
        memory = previous.model_copy(deep=True)
    elif isinstance(previous, dict):
        memory = LearnerMemoryProfile.model_validate(previous)
    else:
        memory = LearnerMemoryProfile(
            user_id=request.user_id,
            subject=request.subject,
            topic=topic or request.topic or "General",
            topic_key=_topic_key(topic or request.topic),
            created_at=_now(),
        )

    # A network retry may replay a persisted tutor turn.  Do not inflate mastery
    # evidence, hint counts, or mistake counts for the same turn.
    summary_turn_id = (session_summary or {}).get("turn_id")
    if summary_turn_id and (
        summary_turn_id in memory.recorded_turn_ids
        or any(
        item.get("turn_id") == summary_turn_id
        for item in memory.recent_session_summaries
        if isinstance(item, dict)
        )
    ):
        return memory

    selected_topic = topic or request.topic or memory.topic
    memory.subject = request.subject or memory.subject
    memory.topic = selected_topic or "General"
    memory.topic_key = _topic_key(memory.topic)
    locale = (request.locale or request.metadata.get("preferred_language") or "").lower()
    if locale.startswith("km"):
        memory.preferred_language = "km"
    elif locale.startswith("en"):
        memory.preferred_language = "en"

    verification = _verification(response)
    verified = verification.get("verified") is True
    status = str(verification.get("status") or "")
    if verified and status in {"correct", "mathematically_valid_but_inefficient"}:
        memory.verified_successful_steps = (
            memory.verified_successful_steps + [_evidence_entry(response, status=status)]
        )[-MAX_EVIDENCE:]
    # ``invalid`` and ``incomplete`` are deterministic outcomes even though
    # they are not verified as *correct*. They are essential evidence for
    # adapting the next step. ``cannot_verify`` deliberately is not counted.
    elif status in {"invalid", "incomplete"}:
        memory.verified_unsuccessful_steps = (
            memory.verified_unsuccessful_steps + [_evidence_entry(response, status=status)]
        )[-MAX_EVIDENCE:]
        misconception = (
            response.metadata.get("misconception_type")
            or response.metadata.get("mistake_category")
            or verification.get("reason_code")
        )
        if misconception:
            # Repetition is meaningful evidence: preserve a bounded streak so
            # the planner can choose targeted error analysis next turn.
            memory.misconceptions = (
                memory.misconceptions + [str(misconception)[:160]]
            )[-MAX_HISTORY:]

    hint_level = request.hint_count if request.hint_count is not None else request.current_state.hint_count
    if request.action == VisualTutorAction.REQUEST_HINT:
        hint_level = int(hint_level or 0) + 1
    memory.hint_levels_used = (memory.hint_levels_used + [max(0, int(hint_level or 0))])[-MAX_HISTORY:]
    if request.action == VisualTutorAction.REQUEST_STUCK_HELP or response.teaching_mode.value == "stuck_help":
        memory.stuck_events += 1

    representation = _representation(response)
    memory.representations_used = _bounded_unique(memory.representations_used, representation, MAX_HISTORY)
    if verified and status in {"correct", "mathematically_valid_but_inefficient"}:
        memory.preferred_successful_representations = _bounded_unique(
            memory.preferred_successful_representations, representation, MAX_HISTORY
        )
    strategy = response.metadata.get("explanation_strategy") or response.metadata.get("tutor_move")
    memory.explanation_strategies_used = _bounded_unique(memory.explanation_strategies_used, strategy, MAX_HISTORY)

    success = len(memory.verified_successful_steps)
    unsuccessful = len(memory.verified_unsuccessful_steps)
    attempts = success + unsuccessful
    rate = round(success / attempts, 3) if attempts else None
    # Readiness is intentionally unavailable until there is enough deterministic evidence.
    readiness = None
    if attempts >= 3:
        readiness = "ready_for_challenge" if rate is not None and rate >= 0.8 else "needs_guided_practice"
    memory.mastery_evidence = {
        "verified_success_count": success,
        "verified_unsuccess_count": unsuccessful,
        "verified_attempt_count": attempts,
        "verified_success_rate": rate,
        "readiness": readiness,
    }
    concept = _concept_key(response, request)
    concept_entry = dict(memory.concept_mastery.get(concept) or {})
    concept_success = int(
        concept_entry.get("correct_attempts") or concept_entry.get("success_count") or 0
    )
    concept_wrong = int(
        concept_entry.get("incorrect_attempts") or concept_entry.get("wrong_count") or 0
    )
    if verified and status in {"correct", "mathematically_valid_but_inefficient"}:
        concept_success += 1
    elif status in {"invalid", "incomplete"}:
        concept_wrong += 1
    concept_attempts = concept_success + concept_wrong
    concept_rate = round(concept_success / concept_attempts, 3) if concept_attempts else None
    concept_readiness = (
        "ready_for_challenge" if concept_attempts >= 3 and concept_rate is not None and concept_rate >= .8
        else "needs_guided_practice" if concept_attempts >= 3
        else "collecting_evidence"
    )
    summary = response.metadata.get("learner_model_summary")
    summary = summary if isinstance(summary, dict) else {}
    misconception = response.metadata.get("misconception_type") or verification.get("reason_code")
    recurring = list(concept_entry.get("recurring_misconceptions") or [])
    if status in {"invalid", "incomplete"} and misconception:
        recurring = _bounded_unique(recurring, str(misconception), MAX_HISTORY)
        # Keep recurrence (two same mistakes) observable without retaining
        # the original student work.
        if len(memory.misconceptions) >= 2 and memory.misconceptions[-1] == memory.misconceptions[-2]:
            recurring = [memory.misconceptions[-1]]
    memory.concept_mastery[concept] = {
        "attempts": concept_attempts,
        "correct_attempts": concept_success,
        "incorrect_attempts": concept_wrong,
        "success_rate": concept_rate,
        "readiness": concept_readiness,
        "confidence_band": str(summary.get("confidence_band") or _confidence_band(attempts=concept_attempts, success_rate=concept_rate)),
        "recurring_misconceptions": recurring,
    }
    if len(memory.concept_mastery) > MAX_CONCEPTS:
        memory.concept_mastery = dict(list(memory.concept_mastery.items())[-MAX_CONCEPTS:])
    memory.confidence_evidence[concept] = float(concept_rate or 0)
    if session_summary:
        safe_summary = {
            key: value for key, value in session_summary.items()
            if key in {"session_id", "status", "completed", "turn_id", "timestamp", "representation", "verified_status"}
        }
        memory.recent_session_summaries = (memory.recent_session_summaries + [safe_summary])[-MAX_SUMMARIES:]
        if summary_turn_id:
            memory.recorded_turn_ids = _bounded_unique(
                memory.recorded_turn_ids, str(summary_turn_id), MAX_SUMMARIES
            )
        active_task = session_summary.get("active_task")
        if isinstance(active_task, dict):
            memory.active_task = {
                key: str(active_task[key])[:120]
                for key in ("id", "type", "task_type")
                if active_task.get(key) is not None
            }
        board_entry = session_summary.get("board_history")
        if isinstance(board_entry, dict):
            safe_board_entry = {
                "board_version": int(board_entry.get("board_version") or 0),
                "representation": str(board_entry.get("representation") or "")[:80],
                "action_types": [
                    str(value)[:80]
                    for value in board_entry.get("action_types", [])
                    if isinstance(value, str)
                ][:24],
            }
            memory.recent_board_history = (
                memory.recent_board_history + [safe_board_entry]
            )[-MAX_BOARD_HISTORY:]
    memory.updated_at = _now()
    return memory


def choose_memory_aware_representation(
    *,
    memory: LearnerMemoryProfile | dict[str, Any] | None,
    candidate: str,
    alternatives: Sequence[str],
    intent: str | None = None,
    stuck: bool = False,
) -> str:
    """Pick a safe alternative when evidence says the prior approach did not help."""
    profile = (
        memory if isinstance(memory, LearnerMemoryProfile)
        else LearnerMemoryProfile.model_validate(memory) if isinstance(memory, dict) else None
    )
    options = [candidate, *[item for item in alternatives if item != candidate]]
    used = profile.representations_used if profile else []
    explain_differently = intent == "request_explain_differently"
    repeated_mistake = bool(profile and len(profile.misconceptions) >= 2 and profile.misconceptions[-1] == profile.misconceptions[-2])
    if repeated_mistake and "error_analysis" in options:
        return "error_analysis"
    if (stuck or explain_differently) and options and options[0] in used:
        for option in options[1:]:
            if option not in used or explain_differently:
                return option
    if explain_differently:
        for option in options:
            if option not in used:
                return option
    return candidate


class LearnerMemoryStore:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._profiles = db["visual_tutor_learner_memory"]

    async def get_for_authenticated_user(self, *, user_id: str, subject: str, topic: str | None) -> LearnerMemoryProfile | None:
        doc = await self._profiles.find_one({"user_id": user_id, "subject_key": _topic_key(subject), "topic_key": _topic_key(topic)})
        if not doc:
            return None
        doc.pop("_id", None)
        doc.pop("subject_key", None)
        return LearnerMemoryProfile.model_validate(doc)

    async def record_turn(self, *, request: VisualTutorTurnRequest, response: VisualTutorTurnResponse, topic: str | None, session_summary: dict[str, Any]) -> LearnerMemoryProfile:
        # This is deliberately scoped using the authenticated user already applied by the route.
        previous = await self.get_for_authenticated_user(user_id=request.user_id, subject=request.subject, topic=topic)
        memory = build_learner_memory_update(previous=previous, response=response, request=request, topic=topic, session_summary=session_summary)
        document = memory.model_dump(mode="json") | {"subject_key": _topic_key(memory.subject)}
        # MongoDB cannot receive the same path in both $set and $setOnInsert.
        # Keep a stable creation time only on the insert operation.
        created_at = document.pop("created_at", None) or _now()
        await self._profiles.update_one(
            {"user_id": request.user_id, "subject_key": _topic_key(memory.subject), "topic_key": memory.topic_key},
            {"$set": document, "$setOnInsert": {"created_at": created_at}},
            upsert=True,
        )
        return memory
