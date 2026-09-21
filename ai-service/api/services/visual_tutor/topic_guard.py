"""Keep a curriculum lesson on its own topic.

When a student opens a topic from the curriculum (the Tutor or Lessons tab),
every turn carries ``is_curriculum_scoped`` plus the lesson's ``topic`` and
``topic_id``. Inside that lesson the tutor solves only problems about that
topic: a functions question asked in "Linear Equations & Systems" is
redirected, not solved. Free-form questions from Home are never topic-locked.

The decision is deterministic and explainable. Each Grade 10-12 topic family
has named-concept keywords in English and Khmer ("strong" evidence). Math
problems with no concept word fall back to the equation's shape ("weak"
evidence: ``2x + 3 = 7`` is linear, ``x^2 - 5x + 6 = 0`` is quadratic). A turn is
redirected only when it is recognisably about a *different* topic; hints, step
answers and questions about the board are never blocked.

Khmer has no word boundaries, so Khmer keywords are matched as plain substrings
and never with ``\\b``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
)


@dataclass(frozen=True)
class _Family:
    key: str
    subject: str
    label_en: str
    label_km: str
    en: re.Pattern[str]
    km: Optional[re.Pattern[str]] = None

    def matches(self, text: str) -> bool:
        return bool(self.en.search(text) or (self.km and self.km.search(text)))


def _family(key: str, subject: str, label_en: str, label_km: str, en: str, km: str = "") -> _Family:
    return _Family(
        key=key,
        subject=subject,
        label_en=label_en,
        label_km=label_km,
        en=re.compile(en, re.IGNORECASE),
        km=re.compile(km) if km else None,
    )


# Ordered most specific first: a lesson's family is the first one its title
# matches, so "Limits of Functions" is limits, not functions.
FAMILIES: tuple[_Family, ...] = (
    # Mathematics
    _family("limits", "mathematics", "limits", "លីមីត",
            r"\\lim|\blim\b|\blimits?\b|\bapproach(?:es|ing)?\b|[a-z]\s*(?:→|->)\s*[-\d∞]",
            r"លីមីត|ខិតទៅ"),
    _family("derivatives", "mathematics", "derivatives", "ដេរីវេ",
            r"\bderivatives?\b|\bdifferentiat|d/d[a-z]\b|\\frac\s*\{\s*d\s*\}|\\prime|\b[fgh]'\s*\(|\btangent line|\brate of change",
            r"ដេរីវេ"),
    _family("integrals", "mathematics", "integrals", "អាំងតេក្រាល",
            r"\bintegra(?:l|ls|te|tion)\b|\\int(?![a-z])|∫|\bantiderivative|\barea under",
            r"អាំងតេក្រាល"),
    _family("trigonometry", "mathematics", "trigonometry", "ត្រីកោណមាត្រ",
            r"\\?\b(?:sin|cos|tan|cot|sec|csc)\b|\btrigonometr|\blaw of (?:sines|cosines)|\btriangles?\b|\bhypotenuse|\bradians?\b",
            r"ត្រីកោណ|ស៊ីនុស|កូស៊ីនុស|តង់សង់"),
    _family("linear_equations", "mathematics", "linear equations", "សមីការលីនេអ៊ែរ",
            r"\blinear\b|\bsystems?\b|\bsimultaneous|\bby substitution|\bby elimination",
            r"លីនេអ៊ែរ|ប្រព័ន្ធសមីការ|សមីការដឺក្រេទី១"),
    _family("quadratics", "mathematics", "quadratic equations", "សមីការដឺក្រេទី២",
            r"\bquadratics?\b|\bparabola|\bvertex\b|\bdiscriminant|\bcompleting the square",
            r"ដឺក្រេទី២|ប៉ារ៉ាបូល|ឌីសគ្រីមីណង់"),
    _family("polynomials", "mathematics", "polynomials", "ពហុធា",
            r"\bpolynomials?\b|\blong division|\bsynthetic division|\bremainder theorem|\bfactor theorem",
            r"ពហុធា"),
    _family("exponentials_logs", "mathematics", "exponentials and logarithms", "អិចស្ប៉ូណង់ស្យែល និងលោការីត",
            r"\blog(?:arithms?)?\b|\bln\b|\\log|\\ln|\bexponentials?\b|\be\^",
            r"លោការីត|អិចស្ប៉ូណង់ស្យែល"),
    _family("sequences", "mathematics", "sequences and series", "ស្វ៊ីត",
            r"\bsequences?\b|\bseries\b|\barithmetic progression|\bgeometric progression|\bnth term|\bcommon (?:difference|ratio)",
            r"ស្វ៊ីត"),
    _family("probability_statistics", "mathematics", "probability and statistics", "ប្រូបាប និងស្ថិតិ",
            r"\bprobabilit|\bmedian\b|\bvariance|\bstandard deviation|\bdice\b|\bcoins?\b|\bcombinations?\b|\bpermutations?\b|\bstatistic",
            r"ប្រូបាប|ស្ថិតិ"),
    _family("vectors", "mathematics", "vectors", "វ៉ិចទ័រ",
            r"\bvectors?\b|\\vec\b|\bdot product|\bcross product",
            r"វ៉ិចទ័រ"),
    _family("matrices", "mathematics", "matrices", "ម៉ាទ្រីស",
            r"\bmatri(?:x|ces)\b|\bdeterminant",
            r"ម៉ាទ្រីស"),
    _family("complex_numbers", "mathematics", "complex numbers", "ចំនួនកុំផ្លិច",
            r"\bcomplex numbers?\b|\bimaginary\b",
            r"កុំផ្លិច"),
    _family("geometry", "mathematics", "geometry", "ធរណីមាត្រ",
            r"\bcircles?\b|\bpolygons?\b|\bperimeter|\bpythagor|\bcircumference|\bspheres?\b|\bcylinders?\b|\bcones?\b",
            r"រង្វង់|ធរណីមាត្រ"),
    _family("functions", "mathematics", "functions", "អនុគមន៍",
            r"\bfunctions?\b|\b[fgh]\s*\(\s*[a-z0-9]+\s*\)|\bdomain\b|\brange\b|\binverse function|\bcomposite function",
            r"អនុគមន៍|ដែនកំណត់"),
    # Physics
    _family("optics", "physics", "optics", "អុបទិច",
            r"\brefract|\breflect|\bsnell|\blens(?:es)?\b|\bmirrors?\b|\brefractive index|\blight rays?|\brays?\b|\bfocal",
            r"ចំណាំងផ្លាត|កញ្ចក់|ពន្លឺ|អុបទិច"),
    _family("electricity", "physics", "electricity", "អគ្គិសនី",
            r"\bcircuits?\b|\bcurrent\b|\bvoltage|\bresist(?:ance|ors?)\b|\bohms?\b|\bcapacit|\bamperes?\b|\bvolts?\b",
            r"ចរន្ត|តង់ស្យុង|រេស៊ីស្តង់|អគ្គិសនី"),
    _family("thermodynamics", "physics", "heat and gases", "កម្ដៅ និងឧស្ម័ន",
            r"\btemperature|\bpressure|\bideal gas|pv\s*=\s*nrt|\bkelvin|\b\d+(?:\.\d+)?\s*k\b|\bheat\b|\bthermodynamic|\bgas(?:es)?\b",
            r"សីតុណ្ហភាព|សម្ពាធ|ឧស្ម័ន|កម្ដៅ|ទែរម៉ូ"),
    _family("waves", "physics", "waves and sound", "រលក",
            r"\bwaves?\b|\bwavelength|\bfrequency|\bamplitude|\bhertz|\bhz\b|\bsound\b",
            r"រលក|ប្រេកង់"),
    _family("momentum", "physics", "momentum", "បរិមាណចលនា",
            r"\bmomentum\b|\bimpulse\b|\bcollisions?\b|\bcollide",
            r"បរិមាណចលនា"),
    _family("energy", "physics", "work and energy", "កម្មន្ត និងថាមពល",
            r"\benergy\b|\bwork done\b|\bkinetic energy|\bpotential energy|\bjoules?\b|\bpower\b|\bwatts?\b",
            r"ថាមពល|កម្មន្ត"),
    _family("gravitation", "physics", "gravitation", "ទំនាញសកល",
            r"\bgravitation|\borbits?\b|\bsatellites?\b|\bescape velocity",
            r"ទំនាញសកល|ផ្កាយរណប"),
    _family("dynamics", "physics", "forces and Newton's laws", "កម្លាំង និងច្បាប់ញូតុន",
            r"\bforces?\b|\bnewton|\bfriction|\bF\s*=\s*m\s*a\b|\btension\b|\bnormal force|\bweight\b|\binclined plane",
            r"កម្លាំង|កកិត|ញូតុន"),
    _family("kinematics", "physics", "motion (kinematics)", "ចលនា",
            r"\bvelocit|\baccelerat|\bspeed\b|\bdisplacement\b|\bdistance\b|\bfree[- ]fall|\bprojectile|\bmotion\b|\bkinematic|\bm/s\b|km/h|\bhow far\b|\btravels?\b",
            r"ល្បឿន|សំទុះ|ចលនា|ចម្ងាយ"),
    # Chemistry
    _family("organic", "chemistry", "organic chemistry", "គីមីសរីរាង្គ",
            r"\borganic|\balkanes?\b|\balkenes?\b|\balkynes?\b|\balcohols?\b|\biupac|\bfunctional groups?|\bch_?3\b|\besters?\b|\bcarboxyl|\bhydrocarbons?\b",
            r"សរីរាង្គ"),
    _family("acids_bases", "chemistry", "acids and bases", "អាស៊ីត និងបាស",
            r"\bacids?\b|\bbases?\b|\bph\b|\btitrat|\bneutrali[sz]|\bnaoh\b|\bhcl\b|\bbuffers?\b",
            r"អាស៊ីត|បាស"),
    _family("solutions_molarity", "chemistry", "solutions and molarity", "សូលុយស្យុង និងកំហាប់",
            r"\bmolarity|\bconcentration|\bsolutions?\b|\bdilut|\bsolutes?\b|\bsolvents?\b",
            r"កំហាប់|សូលុយស្យុង"),
    _family("equilibrium", "chemistry", "chemical equilibrium", "លំនឹងគីមី",
            r"\bequilibri|\bkc\b|\bkp\b|le chatelier|⇌|\breversible",
            r"លំនឹង"),
    _family("electrochemistry", "chemistry", "electrochemistry", "អេឡិចត្រូគីមី",
            r"\bredox|\boxidation|\breduction\b|\belectrodes?\b|\bgalvanic|\belectroly",
            r"អុកស៊ីតកម្ម|អេឡិចត្រូត"),
    _family("thermochemistry", "chemistry", "thermochemistry", "ទែរម៉ូគីមី",
            r"\benthalpy|δh|\bexothermic|\bendothermic|\bcalorimet|\bhess",
            r"អង់តាល់ពី"),
    _family("atomic_structure", "chemistry", "atomic structure", "រចនាសម្ព័ន្ធអាតូម",
            r"\belectron configuration|\bvalence|\batomic (?:number|mass|structure)|\bprotons?\b|\bneutrons?\b|\bisotopes?\b|\bperiodic table|\borbitals?\b|\bz\s*=\s*\d",
            r"អាតូម|អេឡិចត្រុង|តារាងខួប"),
    _family("stoichiometry", "chemistry", "stoichiometry", "ស្តូគ្យូមេទ្រី",
            r"\bstoichiometr|\bmol(?:e|es)?\b|\bmolar mass|\bgrams?\b|\breact(?:s|ion|ions|ant|ants)?\b|\bproduced?\b|\byield\b|\blimiting reagent|\bchemical equation|\bbalanc(?:e|ed|ing)\b",
            r"ស្តូគ្យូមេទ្រី|ស្តូគីយ៉ូមេទ្រី|ម៉ូល|ប្រតិកម្ម|ក្រាម"),
)

_BY_KEY = {family.key: family for family in FAMILIES}

# Topics that legitimately use each other's vocabulary.
RELATED: dict[str, frozenset[str]] = {
    "functions": frozenset({"quadratics", "linear_equations", "exponentials_logs", "polynomials"}),
    "trigonometry": frozenset({"geometry"}),
    "dynamics": frozenset({"kinematics"}),
    "energy": frozenset({"kinematics", "dynamics"}),
    "momentum": frozenset({"kinematics"}),
    "solutions_molarity": frozenset({"stoichiometry"}),
    "stoichiometry": frozenset({"solutions_molarity"}),
    "acids_bases": frozenset({"solutions_molarity", "stoichiometry"}),
}

_NON_TEACHING_ACTIONS = {
    VisualTutorAction.REQUEST_HINT,
    VisualTutorAction.REQUEST_STUCK_HELP,
    VisualTutorAction.EXPLAIN_DIFFERENTLY,
    VisualTutorAction.REQUEST_FINAL_ANSWER,
    VisualTutorAction.GENERATE_PRACTICE,
}

# Imperative openers that mark typed text as a new problem even when the
# gateway forwards it as a step.
_PROBLEM_OPENER_RE = re.compile(
    r"^\s*(?:please\s+)?(?:solve|find|calculate|compute|evaluate|determine|simplify|factor(?:ise|ize)?|prove|graph|differentiate|integrate|what\s+is|how\s+(?:many|much|far|long))\b",
    re.IGNORECASE,
)
_PROBLEM_OPENER_KM_RE = re.compile(r"^\s*(?:ដោះស្រាយ|រក|គណនា|បង្ហាញថា|សង់)")

_POWER_RE = re.compile(r"[a-z]\s*(?:\^|\*\*)\s*\{?\s*(\d+)|[a-z]([²³])", re.IGNORECASE)
_EQUATION_VARIABLE_RE = re.compile(r"(?:\d\s*|\b)[a-z]\b\s*[-+=*/)]|[-+=*/(]\s*\d*\s*[a-z]\b", re.IGNORECASE)
_STOPWORDS = {
    "of", "and", "the", "in", "on", "a", "an", "for", "to", "with", "law", "laws",
    "basic", "intro", "introduction", "math", "maths", "mathematics", "physics",
    "chemistry", "g10", "g11", "g12", "grade",
}


@dataclass(frozen=True)
class TopicGuardDecision:
    allowed: bool
    lesson_topic: str
    lesson_family: Optional[str]
    detected_family: Optional[str] = None
    reason: str = "on_topic"

    @property
    def detected_label_en(self) -> str:
        family = _BY_KEY.get(self.detected_family or "")
        return family.label_en if family else "a different topic"

    @property
    def detected_label_km(self) -> str:
        family = _BY_KEY.get(self.detected_family or "")
        return family.label_km if family else "ប្រធានបទផ្សេង"


def _strong_families(text: str) -> list[str]:
    return [family.key for family in FAMILIES if family.matches(text)]


def _structural_families(text: str) -> list[str]:
    """Classify a bare math problem by the shape of its equation."""
    degrees = [int(m.group(1)) if m.group(1) else (2 if m.group(2) == "²" else 3) for m in _POWER_RE.finditer(text)]
    degree = max(degrees, default=1)
    if degree >= 3:
        return ["polynomials"]
    if degree == 2:
        return ["quadratics"]
    if "=" in text and _EQUATION_VARIABLE_RE.search(text):
        return ["linear_equations"]
    return []


def _lesson_family(topic_text: str) -> Optional[str]:
    for family in FAMILIES:
        if family.matches(topic_text):
            return family.key
    return None


def _words(text: str) -> set[str]:
    words = set()
    for word in re.findall(r"[a-z\u1780-\u17ff]+", text.lower()):
        if len(word) <= 3 or word in _STOPWORDS:
            continue
        words.add(re.sub(r"(?:ions|ion|ing|ed|es|s)$", "", word))
    return words


def _action(request: VisualTutorTurnRequest) -> Optional[VisualTutorAction]:
    try:
        return VisualTutorAction(getattr(request.action, "value", request.action))
    except ValueError:
        return None


def _is_new_problem(request: VisualTutorTurnRequest, message: str) -> bool:
    action = _action(request)
    intent = getattr(request.student_intent, "value", request.student_intent)
    return (
        action in {VisualTutorAction.START, VisualTutorAction.SUBMIT_PROBLEM}
        or intent == VisualTutorStudentIntent.NEW_PROBLEM.value
        or bool(_PROBLEM_OPENER_RE.search(message) or _PROBLEM_OPENER_KM_RE.search(message))
    )


def is_curriculum_scoped(request: VisualTutorTurnRequest) -> bool:
    metadata = request.metadata or {}
    return metadata.get("is_curriculum_scoped") is True or metadata.get("entry_context") == "lesson"


def evaluate_topic_guard(request: VisualTutorTurnRequest) -> Optional[TopicGuardDecision]:
    """Return a decision for curriculum-scoped turns, or None when unscoped."""
    metadata = request.metadata or {}
    if not is_curriculum_scoped(request):
        return None
    # The local limits demo drives its own scripted teaching moment.
    if metadata.get("teaching_moment_id") or metadata.get("entry_point") == "local_curriculum_demo":
        return None

    lesson_topic = str(request.topic or metadata.get("topic") or "").strip()
    topic_id = str(metadata.get("topic_id") or "").strip()
    if not lesson_topic and not topic_id:
        return None
    lesson_text = f"{lesson_topic} {re.sub(r'[-_.]', ' ', topic_id)}"
    lesson_family = _lesson_family(lesson_text)
    display_topic = lesson_topic or topic_id

    def allow(reason: str = "on_topic") -> TopicGuardDecision:
        return TopicGuardDecision(True, display_topic, lesson_family, reason=reason)

    def refuse(detected: Optional[str]) -> TopicGuardDecision:
        return TopicGuardDecision(False, display_topic, lesson_family, detected, "off_topic_for_lesson")

    if _action(request) in _NON_TEACHING_ACTIONS:
        return allow("non_teaching_action")
    message = (request.message or "").strip()
    if not message:
        return allow("no_message")

    strong = _strong_families(message)
    new_problem = _is_new_problem(request, message)

    if lesson_family is None:
        # An admin-published topic outside the taxonomy: keep the student on it
        # when the question is recognisably about something else and shares no
        # words with the topic title.
        if strong and not (_words(message) & _words(lesson_text)):
            return refuse(strong[0])
        return allow("unmapped_topic")

    accepted = {lesson_family} | RELATED.get(lesson_family, frozenset())
    if strong:
        if accepted & set(strong):
            return allow()
        return refuse(strong[0])

    if new_problem and _BY_KEY[lesson_family].subject == "mathematics":
        weak = _structural_families(message)
        if weak and not (accepted & set(weak)):
            return refuse(weak[0])

    # Nothing identifies another topic: a step answer, a question about the
    # board, or wording the taxonomy does not know. Let the tutor handle it.
    return allow("no_competing_topic")


def build_off_topic_message(decision: TopicGuardDecision, language_mode: str = "english") -> dict[str, str]:
    """Bilingual redirect that names the lesson and what the question looked like."""
    is_khmer = (language_mode or "").strip().lower() in {"khmer", "km"}
    topic = decision.lesson_topic

    text_en = (
        f"This lesson is about {topic}. Your question looks like it is about "
        f"{decision.detected_label_en}, so I can't solve it in this lesson. "
        f"Ask me a {topic} problem, or go back to Home to ask about anything else."
    )
    text_km = (
        f"មេរៀននេះគឺអំពី «{topic}»។ សំណួររបស់អ្នកហាក់ដូចជាទាក់ទងនឹង{decision.detected_label_km} "
        f"ដូច្នេះខ្ញុំមិនអាចដោះស្រាយវានៅក្នុងមេរៀននេះបានទេ។ សូមសួរលំហាត់អំពី «{topic}» "
        "ឬត្រឡប់ទៅទំព័រដើមដើម្បីសួរអំពីប្រធានបទផ្សេង។"
    )
    if is_khmer:
        return {
            "display_text": f"{text_km}\n\n{text_en}",
            "student_task": f"សូមសួរលំហាត់អំពី «{topic}»។",
            "board_title": f"តោះផ្តោតលើ «{topic}»",
            "board_content": text_km,
        }
    return {
        "display_text": f"{text_en}\n\n{text_km}",
        "student_task": f"Ask a {topic} problem.",
        "board_title": f"Let's stay on {topic}",
        "board_content": text_en,
    }
