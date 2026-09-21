"""Dynamic RAG curriculum classification and verification gate.

Replaces hardcoded solver regexes with dynamic curriculum knowledge-base queries:
- Tier 1 (Verified): In-scope STEM problem with matching admin-published curriculum content/formulas.
- Tier 2 (Unverified AI): In-scope STEM problem (Math/Physics/Chemistry) without specific curriculum chunks.
- Tier 3 (Out of Scope): Non-STEM queries (chit-chat, history, coding unrelated apps) -> polite refusal.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional

from api.models.curriculum import CurriculumChunk
from api.services.curriculum.curriculum_store import (
    CurriculumStore,
    get_default_curriculum_store,
)

logger = logging.getLogger(__name__)

# Standard high school STEM subjects supported
SUPPORTED_SUBJECTS = {
    "mathematics": [
        "math", "mathematics", "maths", "algebra", "calculus", "geometry", "trigonometry",
        "matrix", "matrices", "quadratic", "linear", "logarithm", "integral", "derivative",
        "limit", "lim", "function", "គណិតវិទ្យា",
    ],
    "physics": [
        "physics", "kinematics", "mechanics", "optics", "electricity", "velocity",
        "acceleration", "gravity", "force", "momentum", "friction", "wavelength",
        "frequency", "circuit", "voltage", "current", "រូបវិទ្យា",
    ],
    "chemistry": [
        "chemistry", "stoichiometry", "reactions", "organic", "moles", "molar",
        "reactant", "product", "h2o", "co2", "acid", "base", "solution",
        "concentration", "molarity", "គីមីវិទ្យា",
    ],
}

# Common STEM indicators (math symbols, science units, formulas, keywords)
_STEM_PATTERNS = [
    r"[-+*/^=<>≤≥∫∑√π]",
    r"\b(?:lim|limite|limit|derivative|integral|solve|factor|evaluate|equation|function|simplify|graph|matrix|matrices|vector|slope|polynomial|quadratic|linear)\b",
    r"\b(?:velocity|speed|acceleration|distance|force|mass|gravity|energy|momentum|friction|wavelength|frequency|kinematics|projectile)\b",
    r"\b(?:m/s|m/s\^2|km/h|mol|molar|molarity|stoichiometry|h2o|co2|o2|n2|fe|caco3|hcl|naoh|acid|base|titration|reaction|reactants)\b",
    r"(?:លីមីត|ដេរីវេ|សមីការ|អនុគមន៍|ល្បឿន|សំទុះ|ចម្ងាយ|ម៉ាស|កម្លាំង|ប្រតិកម្ម|ម៉ូល|ក្រាម|លីត្រ)",
]
_STEM_RE = re.compile("|".join(_STEM_PATTERNS), re.IGNORECASE)

# Scientific unit pattern (e.g. 5 m/s, 10 m, 9.8 m/s^2, 2.5 mol)
_STEM_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:m/s\^2|m/s|km/h|m|cm|mm|s|sec|min|kg|g|mg|mol|mmol|l|ml|n|j|w|v|pa|hz)\b",
    re.IGNORECASE,
)

# Non-STEM markers that indicate chit-chat or off-topic questions
_OFF_TOPIC_RE = re.compile(
    r"\b(?:who\s+is|who\s+was|president|capital\s+of|weather|recipe|cook|bake|baking|movie|song|poem|joke|game|dating|horoscope|crypto|bitcoin|stock\s+market|web\s+scraping|scrape|scraping|react\s+app|flutter\s+widget|python\s+script|code\s+in|beautifulsoup)\b",
    re.IGNORECASE,
)
_OFF_TOPIC_KM_RE = re.compile(
    r"(?:តើ\s*នរណា|ប្រធានាធិបតី|រាជធានី|អាកាសធាតុ|រូបមន្តធ្វើម្ហូប|ភាពយន្ត|ចម្រៀង|កំប្លែង|ហោរាសាស្ត្រ)"
)


_TOPIC_STOPWORDS = {
    "of", "and", "the", "in", "on", "a", "an", "for", "to", "with",
    "basic", "intro", "introduction", "meaning", "concept", "concepts",
    "idea", "ideas", "motion", "law", "laws", "problem", "problems",
}


def _topic_stems(text: str) -> set[str]:
    words = re.findall(r"[\w\u1780-\u17ff]+", text.lower())
    stems = set()
    for w in words:
        if w in _TOPIC_STOPWORDS or len(w) <= 2:
            continue
        stem = re.sub(r"(s|es|ing|ed|tion|tions)$", "", w)
        if stem and stem not in _TOPIC_STOPWORDS:
            stems.add(stem)
    return stems


def _topics_compatible(explicit_topic: str, chunk_topic: str, chunk_subtopic: Optional[str] = None) -> bool:
    if not explicit_topic:
        return True
    exp_norm = explicit_topic.strip().lower()
    if exp_norm in ("general", "general stem", "stem", "all", "unknown"):
        return True
    c_topic_norm = chunk_topic.strip().lower()
    if exp_norm in c_topic_norm or c_topic_norm in exp_norm:
        return True
    if chunk_subtopic:
        c_sub_norm = chunk_subtopic.strip().lower()
        if exp_norm in c_sub_norm or c_sub_norm in exp_norm:
            return True
    exp_stems = _topic_stems(exp_norm)
    chunk_stems = _topic_stems(c_topic_norm)
    if chunk_subtopic:
        chunk_stems |= _topic_stems(chunk_subtopic)
    return bool(exp_stems & chunk_stems)


@dataclass(frozen=True)
class ClassificationResult:
    tier: str  # "verified", "unverified", "out_of_scope"
    subject: str  # "mathematics", "physics", "chemistry", "general_stem"
    topic: Optional[str] = None
    grade: int = 12
    matching_chunks: list[CurriculumChunk] = field(default_factory=list)
    confidence: float = 0.0
    is_khmer: bool = False
    refusal_message_en: Optional[str] = None
    refusal_message_km: Optional[str] = None

    @property
    def is_verified(self) -> bool:
        return self.tier == "verified"

    @property
    def is_in_scope(self) -> bool:
        return self.tier in ("verified", "unverified")


def classify_student_query(
    message: str,
    *,
    grade: Optional[int] = None,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    store: Optional[CurriculumStore] = None,
) -> ClassificationResult:
    """Classify student query into Tier 1 (Verified), Tier 2 (Unverified AI), or Tier 3 (Out of Scope)."""
    text = (message or "").strip()
    is_km = bool(re.search(r"[\u1780-\u17ff]", text))
    active_grade = grade if grade in (10, 11, 12) else 12

    # 1. Check for clear non-STEM off-topic indicators
    if _OFF_TOPIC_RE.search(text) or _OFF_TOPIC_KM_RE.search(text):
        return _build_out_of_scope_result(is_km, reason="off_topic")

    # 2. Check if the message has STEM signals
    has_stem_signals = bool(_STEM_RE.search(text)) or bool(_STEM_UNIT_RE.search(text))

    # Determine subject if explicitly given or inferred
    detected_subject = _detect_subject(text, subject)

    # 3. Query the curriculum knowledge base (RAG)
    active_store = store or get_default_curriculum_store()
    scored_chunks = active_store.search_chunks_by_query(
        text,
        grade=active_grade,
        subject=detected_subject if detected_subject in SUPPORTED_SUBJECTS else None,
        limit=5,
    )

    # 4. Evaluate Tier
    matching = []
    top_score = 0.0
    top_chunk = None
    if scored_chunks:
        explicit_topic_norm = (topic or "").strip().lower()
        if explicit_topic_norm and explicit_topic_norm not in ("general", "general stem", "stem"):
            # Check if any chunk matches the explicit topic
            topic_matched_chunks = [
                (s, c) for s, c in scored_chunks
                if _topics_compatible(explicit_topic_norm, c.topic, c.subtopic)
            ]
            if topic_matched_chunks and topic_matched_chunks[0][0] >= 5.0:
                top_score, top_chunk = topic_matched_chunks[0]
                matching = [c for _, c in topic_matched_chunks]
        elif scored_chunks[0][0] >= 5.0:
            top_score, top_chunk = scored_chunks[0]
            matching = [c for _, c in scored_chunks]

    if matching and top_chunk is not None:
        return ClassificationResult(
            tier="verified",
            subject=top_chunk.subject.lower(),
            topic=top_chunk.topic,
            grade=top_chunk.grade or active_grade,
            matching_chunks=matching,
            confidence=min(1.0, top_score / 15.0),
            is_khmer=is_km,
        )

    # If no exact curriculum chunk matched, but message has STEM indicators:
    if has_stem_signals or (detected_subject in SUPPORTED_SUBJECTS and (subject or "").strip().lower() in SUPPORTED_SUBJECTS):
        target_subject = detected_subject if detected_subject in SUPPORTED_SUBJECTS else "mathematics"
        # Tier 2: Valid STEM problem, but unverified (not in admin curriculum yet)
        return ClassificationResult(
            tier="unverified",
            subject=target_subject,
            topic=topic or "General STEM Problem",
            grade=active_grade,
            matching_chunks=[],
            confidence=0.5,
            is_khmer=is_km,
        )

    # Tier 3: Out of scope
    return _build_out_of_scope_result(is_km, reason="non_stem")


def _detect_subject(text: str, explicit_subject: Optional[str]) -> str:
    """Detect subject from explicit string or message text."""
    explicit_clean = (explicit_subject or "").strip().lower()
    if explicit_clean in SUPPORTED_SUBJECTS:
        return explicit_clean
    lowered = text.lower()
    for subj_canonical, aliases in SUPPORTED_SUBJECTS.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                return subj_canonical
    return "general_stem"


def _build_out_of_scope_result(is_khmer: bool, reason: str = "non_stem") -> ClassificationResult:
    msg_en = (
        "I am ReanAI, your visual tutor for Grade 10–12 Mathematics, Physics, and Chemistry. "
        "I can solve problems and explain each step visually on the whiteboard. "
        "Please ask a problem related to math, physics, or chemistry!"
    )
    msg_km = (
        "ខ្ញុំជា ReanAI គ្រូបង្រៀនរូបភាពសម្រាប់ថ្នាក់ទី១០-១២ លើមុខវិជ្ជា គណិតវិទ្យា រូបវិទ្យា និងគីមីវិទ្យា។ "
        "ខ្ញុំអាចដោះស្រាយលំហាត់ និងពន្យល់មួយជំហានម្តងៗលើក្តារខៀនជីវចល។ "
        "សូមសួរសំណួរ ឬលំហាត់ទាក់ទងនឹងគណិតវិទ្យា រូបវិទ្យា ឬគីមីវិទ្យា!"
    )
    return ClassificationResult(
        tier="out_of_scope",
        subject="general_stem",
        topic=None,
        matching_chunks=[],
        confidence=0.0,
        is_khmer=is_khmer,
        refusal_message_en=msg_en,
        refusal_message_km=msg_km,
    )
