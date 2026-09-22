"""A lesson opened from the curriculum only teaches its own topic.

A student who opens "Linear Equations & Systems" can ask linear-equation
problems there; a functions or limits problem is redirected instead of solved.
Step answers, hints and questions about the board are never blocked.
"""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorLanguageMode,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.topic_guard import evaluate_topic_guard

# The published catalogue (backend curriculum-catalog.service.ts): every
# lesson's own starter problem must be accepted by its own lesson.
CATALOGUE = [
    (12, "Mathematics", "Limits of Functions", "math-g12-limits-of-functions", r"\lim_{x \to 3} \frac{x^2 - 9}{x - 3}"),
    (12, "Mathematics", "Derivatives of Functions", "math-g12-derivatives", r"f(x) = x^3 - 3x^2 + 2, \quad \text{find } f^\prime(2)"),
    (12, "Mathematics", "Integrals & Area Calculation", "math-g12-integrals", r"\int_0^2 (3x^2 + 2x) \, dx"),
    (12, "Physics", "1D Kinematics", "physics-g12-kinematics", "A car accelerates from rest at 2 m/s^2 for 5 seconds. Find its final velocity."),
    (12, "Physics", "Optics & Snell's Law", "physics-g12-optics", "A ray enters glass (n=1.5) from air at 30 degrees. Find the angle of refraction."),
    (12, "Physics", "Thermodynamics & Ideal Gas Law", "physics-g12-thermodynamics", "A 2.0 L container holds 0.5 mol of gas at 300 K. What is the pressure?"),
    (12, "Chemistry", "Stoichiometry & Reaction Tables", "chem-g12-stoichiometry", r"2H_2 + O_2 \to 2H_2O, \quad \text{find moles of water from 4 mol } H_2"),
    (12, "Chemistry", "Acids & Bases (Titration & pH)", "chem-g12-acids-bases", r"\text{What volume of 0.1 M NaOH neutralizes 25 mL of 0.2 M HCl?}"),
    (12, "Chemistry", "Organic Chemistry & Functional Groups", "chem-g12-organic", r"\text{Name the IUPAC compound: } CH_3-CH_2-CH(OH)-CH_3"),
    (11, "Mathematics", "Trigonometry & Law of Cosines", "math-g11-trigonometry", "In triangle ABC, a=5, b=7, and angle C=60 degrees. Find side c."),
    (11, "Physics", "Newton's Laws of Motion", "physics-g11-newton-laws", "A 10 kg block is pushed with a 50 N horizontal force on a frictionless surface. Find acceleration."),
    (11, "Chemistry", "Solutions & Molarity", "chem-g11-solutions-molarity", "How many grams of NaCl are needed to prepare 500 mL of 0.2 M solution?"),
    (10, "Mathematics", "Linear Equations & Systems", "math-g10-linear-equations", "Solve the system: 2x + y = 7 and x - y = 2."),
    (10, "Physics", "Uniform Rectilinear Motion", "physics-g10-uniform-motion", "A train moves at a constant speed of 72 km/h. How far does it travel in 30 minutes?"),
    (10, "Chemistry", "Atomic Structure & Periodic Table", "chem-g10-atomic-structure", "Write the electron configuration of Carbon (Z = 6) and identify valence electrons."),
]

LINEAR = (10, "Mathematics", "Linear Equations & Systems", "math-g10-linear-equations")
LIMITS = (12, "Mathematics", "Limits of Functions", "math-g12-limits-of-functions")
KINEMATICS = (12, "Physics", "1D Kinematics", "physics-g12-kinematics")


def lesson_request(
    lesson: tuple,
    message: str,
    *,
    action: VisualTutorAction = VisualTutorAction.SUBMIT_PROBLEM,
    scoped: bool = True,
    **metadata,
) -> VisualTutorTurnRequest:
    grade, subject, topic, topic_id = lesson[:4]
    return VisualTutorTurnRequest(
        user_id="student-1",
        session_id="topic-guard-session",
        grade=grade,
        subject=subject,
        topic=topic,
        message=message,
        action=action,
        metadata={
            "is_curriculum_scoped": scoped,
            "entry_context": "lesson" if scoped else "ask_question",
            "topic": topic,
            "topic_id": topic_id,
            **metadata,
        },
    )


def blocked(request: VisualTutorTurnRequest) -> bool:
    decision = evaluate_topic_guard(request)
    return decision is not None and not decision.allowed


@pytest.mark.parametrize("grade,subject,topic,topic_id,starter", CATALOGUE)
def test_every_lesson_accepts_its_own_starter_problem(grade, subject, topic, topic_id, starter):
    assert not blocked(lesson_request((grade, subject, topic, topic_id), starter))


@pytest.mark.parametrize(
    "message",
    [
        "Solve 3x + 5 = 20",
        "Solve x + y = 10 and x - y = 2",
        "Solve the system of linear equations 2x + 3y = 12, x - y = 1",
        "ដោះស្រាយប្រព័ន្ធសមីការ 2x + y = 7 និង x - y = 2",
    ],
)
def test_linear_lesson_accepts_linear_problems(message):
    assert not blocked(lesson_request(LINEAR, message))


@pytest.mark.parametrize(
    "message",
    [
        "Find the domain of the function f(x) = sqrt(x - 2)",
        "f(x) = 2x + 1, find f(3)",
        "Find the limit of (x^2-4)/(x-2) as x approaches 2",
        "Solve x^2 - 5x + 6 = 0",
        "Find the derivative of x^3",
        "រកលីមីតនៃ (x^2-9)/(x-3) ពេល x ខិតទៅ 3",
        "រកដែនកំណត់នៃអនុគមន៍ f(x) = 1/x",
        "A car starts from rest and accelerates at 2 m/s^2 for 5 s. Find its final velocity.",
    ],
)
def test_linear_lesson_refuses_other_topics(message):
    assert blocked(lesson_request(LINEAR, message))


def test_limits_lesson_accepts_limits_in_english_and_khmer():
    assert not blocked(lesson_request(LIMITS, "Find the limit of (x^2-4)/(x-2) as x approaches 2"))
    assert not blocked(lesson_request(LIMITS, "រកលីមីតនៃ (x^2-9)/(x-3) ពេល x ខិតទៅ 3"))


@pytest.mark.parametrize(
    "message",
    [
        "Find the derivative of f(x) = x^2 + 3x",
        "Solve 2x + 3 = 7",
        "How many grams of water form when 4 g of hydrogen reacts with oxygen?",
    ],
)
def test_limits_lesson_refuses_other_topics(message):
    assert blocked(lesson_request(LIMITS, message))


def test_kinematics_lesson_refuses_chemistry():
    assert blocked(
        lesson_request(KINEMATICS, "How many grams of water form when 4 g of hydrogen reacts with oxygen?")
    )
    assert not blocked(lesson_request(KINEMATICS, "A bike moves at 5 m/s and accelerates at 1 m/s^2 for 4 s. Find the distance."))


def test_step_answers_hints_and_board_questions_are_never_blocked():
    assert not blocked(lesson_request(LINEAR, "x = 3", action=VisualTutorAction.SUBMIT_STEP))
    assert not blocked(lesson_request(LINEAR, "", action=VisualTutorAction.REQUEST_HINT))
    assert not blocked(lesson_request(LINEAR, "Why did you subtract 5 in step 2?", action=VisualTutorAction.SUBMIT_STEP))


def test_a_follow_up_that_changes_topic_is_blocked():
    assert blocked(
        lesson_request(
            LINEAR,
            "Can you find the domain of the function f(x) = 1/x instead?",
            action=VisualTutorAction.SUBMIT_STEP,
        )
    )


def test_free_form_questions_outside_a_lesson_are_not_topic_locked():
    assert evaluate_topic_guard(
        lesson_request(LINEAR, "Find the domain of the function f(x) = 1/x", scoped=False)
    ) is None


def test_local_curriculum_demo_start_is_exempt():
    request = lesson_request(
        LIMITS,
        "Start local curriculum demo.",
        action=VisualTutorAction.START,
        teaching_moment_id="limits-moment",
    )
    assert not blocked(request)


def test_unknown_admin_topic_falls_back_to_topic_words():
    lesson = (11, "Mathematics", "Mathematical Induction", "math-g11-induction")
    assert not blocked(lesson_request(lesson, "Prove by induction that 1 + 2 + ... + n = n(n+1)/2"))
    assert blocked(lesson_request(lesson, "Find the limit of (x^2-4)/(x-2) as x approaches 2"))


def test_orchestrator_redirects_off_topic_problem_in_a_lesson():
    response = handle_visual_tutor_turn(
        lesson_request(LINEAR, "Find the domain of the function f(x) = sqrt(x - 2)")
    )
    assert response.metadata.get("fallback_reason") == "off_topic_for_lesson"
    assert "Linear Equations & Systems" in response.display_text
    assert response.metadata["topic_guard"]["lesson_topic"] == "Linear Equations & Systems"


def test_orchestrator_redirect_is_khmer_in_khmer_mode():
    request = lesson_request(LINEAR, "រកលីមីតនៃ (x^2-9)/(x-3) ពេល x ខិតទៅ 3")
    request = request.model_copy(update={"language_mode": VisualTutorLanguageMode.KHMER})
    response = handle_visual_tutor_turn(request)
    assert response.metadata.get("fallback_reason") == "off_topic_for_lesson"
    assert response.display_text.startswith("មេរៀននេះ")


def test_orchestrator_still_solves_on_topic_problem_in_a_lesson():
    response = handle_visual_tutor_turn(
        lesson_request(LIMITS, "Find the limit of (x^2-4)/(x-2) as x approaches 2")
    )
    assert response.metadata.get("fallback_reason") != "off_topic_for_lesson"
