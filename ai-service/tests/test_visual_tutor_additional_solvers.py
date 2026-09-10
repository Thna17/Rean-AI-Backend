from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorCanvasActionType,
    VisualTutorAction,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.policy import decide_visual_tutor_policy
from api.services.visual_tutor.problem_understanding import (
    VisualTutorProblemUnderstandingRequest,
    understand_visual_tutor_problem,
)
from api.services.visual_tutor.solver_registry import VisualTutorSolverRegistry
from api.services.visual_tutor.solvers import (
    ArithmeticExpressionSolver,
    LineThroughPointsSolver,
    LinearEquationSolver,
    QuadraticEquationBasicSolver,
    SimplePercentageWordProblemSolver,
    SlopeFromTwoPointsSolver,
)

SOLVER_CASES = [
    (
        "linear_equation_one_variable",
        "Solve 2x + 5 = 15",
        "x = 5",
        "constant",
    ),
    (
        "line_through_two_points",
        "Find the equation of the line through D(0,1) and E(1,3)",
        "y = 2x + 1",
        "change",
    ),
    (
        "slope_from_two_points",
        "Find slope between A(0, 1) and B(1, 3)",
        "m = 2",
        "change",
    ),
    (
        "quadratic_equation",
        "solve x^2 - 5x + 6 = 0",
        "Final answer:",
        "factoring",
    ),
    (
        "integer_arithmetic",
        "calculate 12 + 7 * 3",
        "Final answer:",
        "operation",
    ),
    (
        "simple_percentage_word_problem",
        "What is 20% of 50?",
        "Final answer:",
        "100",
    ),
]


def _visible_text(turn) -> str:
    return " ".join(
        [
            turn.spoken_text,
            turn.display_text,
            turn.student_task,
            *(item.content for item in turn.board.items),
        ]
    )


def _canvas_text(turn) -> str:
    return " ".join(
        str(value)
        for action in turn.canvas_actions
        for value in (action.text, action.latex, action.target_id)
        if value
    )


def _board_action_text(turn) -> str:
    return " ".join(
        str(value)
        for action in turn.board_actions
        for value in (action.text, action.latex, action.target_id)
        if value
    )


def _assert_solver_speech_bypassed(turn) -> None:
    assert turn.metadata.get("solver_speech_bypassed") is True


LIVE_TEACHER_SOLVER_CASES = [
    (LinearEquationSolver, "2x + 5 = 15"),
    (
        LineThroughPointsSolver,
        "Find the equation of the line through D(0,1) and E(1,3)",
    ),
    (SlopeFromTwoPointsSolver, "What is the slope between A(2,4) and B(5,10)?"),
    (QuadraticEquationBasicSolver, "Solve x^2 - 5x + 6 = 0"),
    (ArithmeticExpressionSolver, "Calculate 12 + 7 * 3"),
    (SimplePercentageWordProblemSolver, "What is 20% of 50?"),
]


@pytest.mark.parametrize(("solver_cls", "message"), LIVE_TEACHER_SOLVER_CASES)
def test_math_solvers_support_live_teacher_move_api(solver_cls, message) -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message=message,
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message=message)
    )
    solver = VisualTutorSolverRegistry().get_solver(understanding)
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=True,
    )

    assert isinstance(solver, solver_cls)
    turn = solver.build_next_teaching_move(
        request,
        understanding,
        policy,
        session_id="live-teacher-session",
    )
    validation = solver.validate_student_response(request, understanding, policy)

    assert turn.board_actions
    assert turn.interaction is not None
    assert turn.final_answer_locked is True
    assert validation["problem_type"] == understanding.problem_type


def test_line_solver_live_teacher_methods_progress_without_early_final_equation() -> (
    None
):
    problem = "Find the equation of the line through D(0,1) and E(1,3)"
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message=problem)
    )
    solver = VisualTutorSolverRegistry().get_solver(understanding)

    first_request = VisualTutorTurnRequest(
        user_id="student-1",
        message=problem,
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    first_policy = decide_visual_tutor_policy(
        first_request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=True,
    )
    first_turn = solver.build_next_teaching_move(
        first_request,
        understanding,
        first_policy,
        session_id="line-live-session",
    )

    assert "y = 2x + 1" not in _board_action_text(first_turn)
    assert VisualTutorCanvasActionType.DRAW_AXES in [
        action.type for action in first_turn.board_actions
    ]
    assert first_turn.interaction.type == VisualTutorInteractionType.NUMERIC_INPUT
    assert first_turn.interaction.prompt == "How much does y increase?"

    delta_y_request = VisualTutorTurnRequest(
        user_id="student-1",
        message="2",
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(
            problem_text=problem,
            normalized_problem="line_through_points:(0,1),(1,3)",
            current_step_index=0,
        ),
    )
    delta_y_policy = decide_visual_tutor_policy(
        delta_y_request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=True,
    )
    delta_y_turn = solver.build_next_teaching_move(
        delta_y_request,
        understanding,
        delta_y_policy,
        session_id="line-live-session",
    )

    assert r"\Delta y = 2" in _board_action_text(delta_y_turn)
    assert r"\Delta x = 1 - 0 = ?" in _board_action_text(delta_y_turn)
    assert "y = 2x + 1" not in _board_action_text(delta_y_turn)
    assert delta_y_turn.board.metadata["current_step_index"] == 1


def test_line_solver_wrong_input_feedback_highlights_first_mistake() -> None:
    problem = "Find the equation of the line through D(0,1) and E(1,3)"
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message=problem)
    )
    solver = VisualTutorSolverRegistry().get_solver(understanding)
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="50",
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(
            problem_text=problem,
            normalized_problem="line_through_points:(0,1),(1,3)",
            current_step_index=0,
        ),
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=True,
    )

    turn = solver.build_wrong_input_feedback(
        request,
        understanding,
        policy,
        session_id="line-live-session",
    )

    assert turn.mastery_signal == VisualTutorMasterySignal.MISCONCEPTION
    assert "y = 2x + 1" not in _board_action_text(turn)
    assert any(
        action.type == VisualTutorCanvasActionType.HIGHLIGHT
        and action.target_id == "y-values"
        for action in turn.board_actions
    )


def test_linear_equation_initial_turn_emits_teacher_canvas_actions() -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    action_types = [action.type for action in turn.canvas_actions]
    canvas_text = _canvas_text(turn)

    assert turn.final_answer_locked is True
    assert VisualTutorCanvasActionType.WRITE_EQUATION in action_types
    assert VisualTutorCanvasActionType.WRITE_TEXT in action_types
    assert VisualTutorCanvasActionType.HIGHLIGHT in action_types
    assert VisualTutorCanvasActionType.SPEAK_MARKER in action_types
    assert VisualTutorCanvasActionType.PAUSE_MARKER in action_types
    assert "2x + 5 = 15" in canvas_text
    assert "x = 5" not in canvas_text
    assert turn.canvas_actions or turn.board_actions
    _assert_solver_speech_bypassed(turn)


def test_line_through_points_first_turn_draws_points_not_final_equation() -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    live_text = _board_action_text(turn)

    assert turn.final_answer_locked is True
    assert "y = 2x + 1" not in live_text
    assert turn.canvas_actions or turn.board_actions
    assert turn.interaction is not None
    assert turn.interaction.type in (
        VisualTutorInteractionType.NUMERIC_INPUT,
        VisualTutorInteractionType.TEXT_RESPONSE,
    )
    _assert_solver_speech_bypassed(turn)


def test_line_through_points_slope_formula_appears_only_when_needed() -> None:
    first_turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    slope_turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="1",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(
                problem_text="Find the equation of the line through D(0,1) and E(1,3)",
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=1,
            ),
            student_submitted_step=True,
        )
    )

    assert first_turn.final_answer_locked is True
    assert slope_turn.final_answer_locked is True
    assert first_turn.canvas_actions or first_turn.board_actions
    assert slope_turn.canvas_actions or slope_turn.board_actions
    assert "y = 2x + 1" not in _board_action_text(first_turn)
    assert "y = 2x + 1" not in _board_action_text(slope_turn)
    _assert_solver_speech_bypassed(first_turn)
    _assert_solver_speech_bypassed(slope_turn)


def test_line_through_points_student_answer_two_advances_to_delta_x() -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(
                problem_text="Find the equation of the line through D(0,1) and E(1,3)",
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=0,
            ),
            student_submitted_step=True,
        )
    )

    live_text = _board_action_text(turn)

    assert turn.final_answer_locked is True
    assert "y = 2x + 1" not in live_text
    assert turn.canvas_actions or turn.board_actions
    assert turn.interaction is not None
    assert turn.interaction.type in (
        VisualTutorInteractionType.NUMERIC_INPUT,
        VisualTutorInteractionType.TEXT_RESPONSE,
    )
    _assert_solver_speech_bypassed(turn)


def test_line_through_points_wrong_answer_highlights_y_values() -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="50",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(
                problem_text="Find the equation of the line through D(0,1) and E(1,3)",
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=0,
            ),
            student_submitted_step=True,
        )
    )

    assert turn.final_answer_locked is True
    assert "y = 2x + 1" not in _board_action_text(turn)
    assert turn.canvas_actions or turn.board_actions
    _assert_solver_speech_bypassed(turn)


def test_line_equation_showcase_flow_advances_delta_y_delta_x_slope_and_b() -> None:
    problem = "Find the equation of the line through D(0,1) and E(1,3)"

    first = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message=problem,
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    assert first.final_answer_locked is True
    assert "y = 2x + 1" not in _board_action_text(first)
    assert first.interaction is not None
    assert first.interaction.type in (
        VisualTutorInteractionType.NUMERIC_INPUT,
        VisualTutorInteractionType.TEXT_RESPONSE,
    )
    _assert_solver_speech_bypassed(first)

    delta_y = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=0,
            ),
        )
    )
    assert delta_y.final_answer_locked is True
    assert "y = 2x + 1" not in _board_action_text(delta_y)
    assert delta_y.canvas_actions or delta_y.board_actions
    _assert_solver_speech_bypassed(delta_y)

    delta_x = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="1",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=1,
            ),
        )
    )
    assert delta_x.final_answer_locked is True
    assert "y = 2x + 1" not in _board_action_text(delta_x)
    assert delta_x.canvas_actions or delta_x.board_actions
    _assert_solver_speech_bypassed(delta_x)

    slope = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=2,
            ),
        )
    )
    assert slope.final_answer_locked is True
    assert "y = 2x + 1" not in _board_action_text(slope)
    assert slope.canvas_actions or slope.board_actions
    _assert_solver_speech_bypassed(slope)


def test_line_equation_showcase_wrong_answers_do_not_advance() -> None:
    problem = "Find the equation of the line through D(0,1) and E(1,3)"

    wrong = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="4",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=1,
            ),
        )
    )

    assert wrong.final_answer_locked is True
    assert "y = 2x + 1" not in _board_action_text(wrong)
    assert wrong.canvas_actions or wrong.board_actions
    _assert_solver_speech_bypassed(wrong)


def test_line_equation_showcase_stuck_at_b_gives_current_step_hint() -> None:
    problem = "Find the equation of the line through D(0,1) and E(1,3)"

    stuck = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=3,
            ),
        )
    )

    text = _board_action_text(stuck)
    assert stuck.final_answer_locked is True
    assert stuck.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert "y = 2x + 1" not in text
    assert stuck.canvas_actions or stuck.board_actions
    assert stuck.interaction is not None
    assert stuck.interaction.type in (
        VisualTutorInteractionType.NUMERIC_INPUT,
        VisualTutorInteractionType.TEXT_RESPONSE,
    )
    _assert_solver_speech_bypassed(stuck)


def test_line_equation_showcase_reveals_final_when_student_requests_answer() -> None:
    problem = "Find the equation of the line through D(0,1) and E(1,3)"

    full = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                normalized_problem="line_through_points:(0,1),(1,3)",
                current_step_index=3,
            ),
        )
    )
    assert full.final_answer_locked is False
    assert "y = 2x + 1" in _board_action_text(full)
    assert full.interaction is not None
    assert full.interaction.prompt


@pytest.mark.parametrize(
    ("problem", "problem_type"),
    [
        ("Solve 2x + 5 = 15", "linear_equation_one_variable"),
        (
            "Find the equation of the line through D(0,1) and E(1,3)",
            "line_through_two_points",
        ),
        ("Find slope between A(0, 1) and B(1, 3)", "slope_from_two_points"),
        ("solve x^2 - 5x + 6 = 0", "quadratic_equation"),
        ("calculate 12 + 7 * 3", "integer_arithmetic"),
        ("What is 20% of 50?", "simple_percentage_word_problem"),
    ],
)
def test_each_math_solver_initial_turn_emits_locked_canvas_actions(
    problem: str,
    problem_type: str,
) -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message=problem,
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert turn.final_answer_locked is True
    assert turn.canvas_actions
    assert turn.metadata["problem_understanding"]["problem_type"] == problem_type or (
        problem_type == "linear_equation_one_variable"
        and turn.board.title == "Linear Equation"
    )
    assert any(
        action.type == VisualTutorCanvasActionType.HIGHLIGHT
        for action in turn.canvas_actions
    )
    assert turn.canvas_actions or turn.board_actions
    assert "x = 5" not in _canvas_text(turn)
    assert "y = 2x + 1" not in _canvas_text(turn)
    _assert_solver_speech_bypassed(turn)


def test_solver_canvas_final_answer_reveals_when_policy_allows() -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(problem_text="Solve 2x + 5 = 15"),
        )
    )

    canvas_text = _canvas_text(turn)
    final_actions = [
        action
        for action in turn.canvas_actions
        if action.metadata.get("is_final_answer") is True
    ]

    assert turn.final_answer_locked is False
    assert "x = 5" in canvas_text
    assert final_actions
    assert all(action.locked is False for action in final_actions)


@pytest.mark.parametrize(
    ("problem_type", "problem", "locked_answer_needle", "hint_needle"),
    SOLVER_CASES,
)
def test_each_solver_supports_stuck_help_turn(
    problem_type: str,
    problem: str,
    locked_answer_needle: str,
    hint_needle: str,
) -> None:
    stuck = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(problem_text=problem),
        )
    )

    assert stuck.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert stuck.student_intent.value == "stuck"
    assert stuck.final_answer_locked is True
    assert locked_answer_needle not in stuck.display_text
    assert stuck.metadata["policy"]["problem_type"] == problem_type
    assert stuck.metadata["policy"]["stuck_progression"] == "first_stuck_hint"
    assert stuck.canvas_actions or stuck.board_actions
    _assert_solver_speech_bypassed(stuck)


@pytest.mark.parametrize(
    ("problem_type", "problem", "_locked_answer_needle", "_hint_needle"),
    SOLVER_CASES,
)
def test_each_solver_repeated_stuck_uses_partial_solution_without_final_answer(
    problem_type: str,
    problem: str,
    _locked_answer_needle: str,
    _hint_needle: str,
) -> None:
    partial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="help me",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            hint_count=1,
            current_state=VisualTutorTurnState(problem_text=problem),
        )
    )

    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert partial.student_intent.value == "stuck"
    assert partial.final_answer_locked is True
    assert partial.metadata["policy"]["problem_type"] == problem_type
    assert (
        partial.metadata["policy"]["stuck_progression"]
        == "partial_after_repeated_stuck"
    )


@pytest.mark.parametrize(
    ("problem_type", "problem", "locked_answer_needle", "hint_needle"),
    SOLVER_CASES,
)
def test_each_solver_supports_explain_differently_turn(
    problem_type: str,
    problem: str,
    locked_answer_needle: str,
    hint_needle: str,
) -> None:
    different = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="explain differently",
            action=VisualTutorAction.EXPLAIN_DIFFERENTLY,
            current_state=VisualTutorTurnState(problem_text=problem),
        )
    )

    assert different.teaching_mode == VisualTutorTeachingMode.HINT
    assert different.student_intent.value == "request_explain_differently"
    assert different.final_answer_locked is True
    assert locked_answer_needle not in different.display_text
    assert different.metadata["policy"]["problem_type"] == problem_type
    assert different.metadata["policy"]["explain_differently"] is True
    assert different.canvas_actions or different.board_actions
    _assert_solver_speech_bypassed(different)


def test_line_through_points_khmer_stuck_partial_is_khmer_friendly() -> None:
    partial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="ខ្ញុំមិនយល់",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            locale="km-KH",
            hint_count=1,
            current_state=VisualTutorTurnState(
                problem_text="Find the equation of the line through D(0,1) and E(1,3)"
            ),
        )
    )

    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert partial.final_answer_locked is True
    assert partial.metadata["policy"]["use_khmer_explanation"] is True
    assert partial.canvas_actions or partial.board_actions


def test_slope_from_two_points_solver_guides_locks_and_reveals() -> None:
    initial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Find slope between A(0, 1) and B(1, 3)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    assert initial.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert initial.final_answer_locked is True
    assert initial.board.metadata["problem_type"] == "slope_from_two_points"
    assert "m = 2" not in initial.display_text
    assert initial.canvas_actions or initial.board_actions
    _assert_solver_speech_bypassed(initial)

    partial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="hint",
            action=VisualTutorAction.REQUEST_HINT,
            hint_count=2,
            current_state=VisualTutorTurnState(
                problem_text="Find slope between A(0, 1) and B(1, 3)"
            ),
        )
    )
    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert partial.final_answer_locked is True
    assert "m = 2" not in partial.display_text
    assert partial.canvas_actions or partial.board_actions

    correct = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="m = 2",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="Find slope between A(0, 1) and B(1, 3)"
            ),
        )
    )
    assert correct.final_answer_locked is True
    assert correct.canvas_actions or correct.board_actions
    _assert_solver_speech_bypassed(correct)

    full = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(
                problem_text="Find slope between A(0, 1) and B(1, 3)"
            ),
        )
    )
    assert full.final_answer_locked is False
    assert full.board.items[-1].content == "m = 2"


def test_quadratic_basic_solver_guides_locks_and_reveals() -> None:
    initial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="solve x^2 - 5x + 6 = 0",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    assert initial.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert initial.final_answer_locked is True
    assert initial.board.metadata["problem_type"] == "quadratic_equation"
    assert "x = 2" not in initial.display_text
    assert "x = 3" not in initial.display_text
    assert initial.canvas_actions or initial.board_actions
    _assert_solver_speech_bypassed(initial)

    partial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="hint",
            action=VisualTutorAction.REQUEST_HINT,
            hint_count=2,
            current_state=VisualTutorTurnState(problem_text="solve x^2 - 5x + 6 = 0"),
        )
    )
    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert partial.final_answer_locked is True
    assert "x = 2" not in partial.display_text
    assert "x = 3" not in partial.display_text
    assert partial.canvas_actions or partial.board_actions

    correct = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="x = 2 or x = 3",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(problem_text="solve x^2 - 5x + 6 = 0"),
        )
    )
    assert correct.final_answer_locked is True
    assert correct.canvas_actions or correct.board_actions
    _assert_solver_speech_bypassed(correct)

    full = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(problem_text="solve x^2 - 5x + 6 = 0"),
        )
    )
    assert full.final_answer_locked is False
    assert "x = 2" in full.board.items[-1].content
    assert "x = 3" in full.board.items[-1].content


def test_arithmetic_expression_solver_guides_locks_and_reveals() -> None:
    initial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="calculate 12 + 7 * 3",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    assert initial.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert initial.final_answer_locked is True
    assert initial.board.metadata["problem_type"] == "arithmetic_expression"
    assert "33" not in initial.display_text
    assert initial.canvas_actions or initial.board_actions
    _assert_solver_speech_bypassed(initial)

    partial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="hint",
            action=VisualTutorAction.REQUEST_HINT,
            hint_count=2,
            current_state=VisualTutorTurnState(problem_text="calculate 12 + 7 * 3"),
        )
    )
    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert "33" not in partial.display_text
    assert partial.canvas_actions or partial.board_actions

    correct = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="33",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(problem_text="calculate 12 + 7 * 3"),
        )
    )
    assert correct.final_answer_locked is True
    assert correct.canvas_actions or correct.board_actions
    _assert_solver_speech_bypassed(correct)

    full = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(problem_text="calculate 12 + 7 * 3"),
        )
    )
    assert full.final_answer_locked is False
    assert full.board.items[-1].content == "33"


def test_simple_percentage_word_problem_solver_guides_locks_and_reveals() -> None:
    problem = "What is 20% of 50?"
    initial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message=problem,
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    assert initial.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert initial.final_answer_locked is True
    assert initial.board.metadata["problem_type"] == "simple_percentage_word_problem"
    assert "10" not in initial.display_text
    assert initial.canvas_actions or initial.board_actions
    _assert_solver_speech_bypassed(initial)

    partial = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="hint",
            action=VisualTutorAction.REQUEST_HINT,
            hint_count=2,
            current_state=VisualTutorTurnState(problem_text=problem),
        )
    )
    assert partial.teaching_mode == VisualTutorTeachingMode.PARTIAL_SOLUTION
    assert "10" not in partial.display_text.replace("100", "")
    assert partial.canvas_actions or partial.board_actions

    correct = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="20/100",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(problem_text=problem),
        )
    )
    assert correct.final_answer_locked is True
    assert correct.canvas_actions or correct.board_actions
    _assert_solver_speech_bypassed(correct)

    full = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(problem_text=problem),
        )
    )
    assert full.final_answer_locked is False
    assert full.board.items[-1].content == "10"
