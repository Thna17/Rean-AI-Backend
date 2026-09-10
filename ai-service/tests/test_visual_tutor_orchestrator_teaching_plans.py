from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


def _turn(*, action, message, state=None, **kwargs):
    return handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-plan-test",
            session_id="plan-test-session",
            subject="Mathematics",
            topic="Linear Equations",
            action=action,
            message=message,
            current_state=state or VisualTutorTurnState(problem_text="2x + 10 = 20"),
            metadata={"grade": 10, **kwargs},
        )
    )


def test_each_real_orchestrated_turn_carries_a_valid_persistable_teaching_plan():
    response = _turn(
        action=VisualTutorAction.SUBMIT_PROBLEM,
        message="2x + 10 = 20",
        state=VisualTutorTurnState(),
    )

    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    assert response.metadata["teaching_plan_source"] == "server_reconciled"
    # A new learner begins with a concrete visual before symbolic manipulation.
    assert plan.representation.value == "balance_scale"
    assert len([a for a in plan.board_actions if a.type.value == "student_task"]) == 1
    assert plan.hidden_answer_policy.deterministic_policy_permits_final_reveal is False
    assert response.metadata["teaching_plan_rationale"]["grade"] == 10


def test_strategy_changes_for_wrong_stuck_and_explain_differently_states():
    wrong = _turn(
        action=VisualTutorAction.SUBMIT_STEP,
        message="2x = 20",
        state=VisualTutorTurnState(
            problem_text="2x + 10 = 20", student_submitted_step=True
        ),
    )
    stuck = _turn(
        action=VisualTutorAction.REQUEST_STUCK_HELP,
        message="I am stuck",
    )
    different = _turn(
        action=VisualTutorAction.EXPLAIN_DIFFERENTLY,
        message="Explain differently",
        strategy_history=[{"representation": "equation_transformation"}],
    )

    assert validate_teaching_plan(wrong.metadata["teaching_plan"]).representation.value == "error_analysis"
    assert validate_teaching_plan(stuck.metadata["teaching_plan"]).representation.value == "worked_example"
    assert validate_teaching_plan(different.metadata["teaching_plan"]).representation.value == "balance_scale"
    assert wrong.final_answer_locked is True
    assert stuck.final_answer_locked is True


def test_khmer_plan_keeps_math_notation_but_records_language_evidence():
    response = _turn(
        action=VisualTutorAction.SUBMIT_PROBLEM,
        message="2x + 10 = 20",
        state=VisualTutorTurnState(),
        preferred_language="km",
    )
    plan = validate_teaching_plan(response.metadata["teaching_plan"])

    assert response.metadata["teaching_plan_rationale"]["language"] == "km"
    assert any("2x" in (action.latex or action.text or "") for action in plan.board_actions)
