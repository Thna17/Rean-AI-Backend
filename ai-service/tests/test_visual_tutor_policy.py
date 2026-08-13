from __future__ import annotations

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorStudentIntent,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.policy import decide_visual_tutor_policy


def test_direct_solve_this_keeps_final_answer_locked() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Please solve this fully: x^2 - 5x + 6 = 0",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        has_problem=True,
        problem_type="quadratic_equation",
        known_solver_available=True,
    )

    assert policy.final_answer_locked is True
    assert policy.full_solution_allowed is False
    assert policy.reveal_final is False
    assert policy.should_ask_question is True
    assert policy.request_student_step is True
    assert policy.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION


def test_unsupported_problem_still_asks_useful_guiding_question() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Can you help with this strange puzzle?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        has_problem=True,
        problem_type="unsupported",
        known_solver_available=False,
    )

    assert policy.final_answer_locked is True
    assert policy.should_ask_question is True
    assert policy.request_student_step is True
    assert policy.give_hint is False
    assert policy.reason == "ask_guiding_question_first"
    assert policy.metadata["problem_type"] == "unsupported"
    assert policy.metadata["known_solver_available"] is False


def test_repeated_hints_unlock_partial_solution_across_problem_type() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="hint please",
            action=VisualTutorAction.REQUEST_HINT,
            hint_count=2,
        ),
        has_problem=True,
        problem_type="word_problem_unknown",
        known_solver_available=False,
    )

    assert policy.final_answer_locked is True
    assert policy.partial_solution_allowed is True
    assert policy.full_solution_allowed is False
    assert policy.reveal_partial is True
    assert policy.give_hint is False
    assert policy.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION


def test_repeated_wrong_attempts_unlock_partial_solution_across_problem_type() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I tried the wrong setup",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(wrong_attempts=1),
        ),
        has_problem=True,
        is_correct_step=False,
        problem_type="slope_from_two_points",
        known_solver_available=True,
    )

    assert policy.final_answer_locked is True
    assert policy.partial_solution_allowed is True
    assert policy.full_solution_allowed is False
    assert policy.diagnose_misconception is True
    assert policy.should_check_step is True
    assert policy.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION


def test_final_answer_request_reveals_adaptively() -> None:
    requested = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
        ),
        has_problem=True,
        problem_type="quadratic_equation",
    )
    explicitly_allowed = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
        ),
        has_problem=True,
        problem_type="quadratic_equation",
    )
    hint_threshold = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            hint_count=3,
        ),
        has_problem=True,
        problem_type="quadratic_equation",
    )
    wrong_threshold = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            current_state=VisualTutorTurnState(wrong_attempts=2),
        ),
        has_problem=True,
        problem_type="quadratic_equation",
    )

    for policy in [requested, explicitly_allowed, hint_threshold, wrong_threshold]:
        assert policy.final_answer_locked is False
        assert policy.full_solution_allowed is True
        assert policy.reveal_final is True
        assert policy.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION
        assert policy.reason == "final_answer_requested"


def test_policy_switches_to_khmer_explanation_mode() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="សូមជួយពន្យល់លំហាត់នេះ",
            locale="km-KH",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        has_problem=True,
        problem_type="word_problem_unknown",
        known_solver_available=False,
    )

    assert policy.use_khmer_explanation is True
    assert policy.metadata["use_khmer_explanation"] is True


def test_stuck_intent_does_not_reveal_final_answer_immediately() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
            student_submitted_step=True,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert policy.final_answer_locked is True
    assert policy.reveal_final is False


def test_unrelated_input_does_not_advance_or_unlock_partial_solution() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="50",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
            student_submitted_step=True,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
        input_understanding=VisualTutorInputUnderstandingResult(
            student_intent=VisualTutorStudentIntent.UNKNOWN,
            input_relevance=VisualTutorInputRelevance.UNRELATED,
            confidence=0.84,
            extracted_numbers=["50"],
            explanation="The number does not match the current step.",
            metadata={"validation_result": "unrelated_numeric_input"},
        ),
    )

    assert policy.should_check_step is False
    assert policy.should_redirect_input is True
    assert policy.partial_solution_allowed is False
    assert policy.final_answer_locked is True
    assert policy.reason == "unrelated_to_current_step"


def test_wrong_relevant_step_counts_as_attempt_path() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2x = 15",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
            student_submitted_step=True,
        ),
        has_problem=True,
        is_correct_step=False,
        problem_type="linear_equation_one_variable",
        input_understanding=VisualTutorInputUnderstandingResult(
            student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            input_relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=0.82,
            extracted_equations=["2x = 15"],
            explanation="Related equation but wrong step.",
            metadata={"validation_result": "incorrect_relevant_step"},
        ),
    )

    assert policy.should_check_step is True
    assert policy.diagnose_misconception is True
    assert policy.reason == "misconception_detected"


def test_early_numeric_final_answer_guess_stays_locked() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="4",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
            student_submitted_step=True,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
        input_understanding=VisualTutorInputUnderstandingResult(
            student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            input_relevance=VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER,
            confidence=0.82,
            extracted_numbers=["4"],
            explanation="Possible final answer.",
            metadata={"validation_result": "incorrect_final_answer"},
        ),
    )

    assert policy.possible_final_answer is True
    assert policy.should_check_step is False
    assert policy.final_answer_locked is True
    assert policy.reason == "final_answer_attempt_locked"
    assert policy.reveal_partial is False
    assert policy.give_hint is True
    assert policy.should_ask_question is True
    assert policy.should_check_step is False


def test_khmer_stuck_message_prefers_khmer_explanation() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="ខ្ញុំមិនយល់",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
            student_submitted_step=True,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert policy.final_answer_locked is True
    assert policy.use_khmer_explanation is True
    assert policy.metadata["use_khmer_explanation"] is True
    assert policy.metadata["stuck_reason"] == "khmer_does_not_understand"


def test_repeated_stuck_unlocks_partial_solution_not_final_answer() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="help me",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            hint_count=1,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert policy.partial_solution_allowed is True
    assert policy.reveal_partial is True
    assert policy.final_answer_locked is True
    assert policy.full_solution_allowed is False
    assert policy.reveal_final is False
    assert policy.metadata["stuck_progression"] == "partial_after_repeated_stuck"


def test_stuck_after_wrong_attempt_triggers_misconception_or_partial_solution() -> None:
    misconception = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I don't understand",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                wrong_attempts=1,
            ),
            student_submitted_step=True,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )
    partial = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I don't understand",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            hint_count=1,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                wrong_attempts=1,
            ),
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert misconception.teaching_mode == VisualTutorTeachingMode.MISCONCEPTION_FIX
    assert misconception.diagnose_misconception is True
    assert misconception.final_answer_locked is True
    assert misconception.should_check_step is False
    assert (
        misconception.metadata["stuck_progression"]
        == "misconception_after_wrong_attempt"
    )

    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert partial.partial_solution_allowed is True
    assert partial.final_answer_locked is True


def test_show_answer_reveals_after_student_request() -> None:
    requested = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            hint_count=2,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )
    threshold = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            hint_count=3,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )
    explicit_unlock = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    for policy in [requested, threshold, explicit_unlock]:
        assert policy.final_answer_locked is False
        assert policy.full_solution_allowed is True
        assert policy.reveal_final is True
        assert policy.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION
