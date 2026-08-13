import pytest
from pydantic import ValidationError

from api.models.visual_tutor import VisualTutorSessionCreateRequest


def test_draft_session_is_explicitly_safe_without_a_problem() -> None:
    request = VisualTutorSessionCreateRequest(
        user_id="student-1",
        session_mode="draft",
        subject="Mathematics",
    )

    assert request.session_mode == "draft"
    assert request.problem_text is None


def test_confirmed_session_requires_a_problem() -> None:
    with pytest.raises(ValidationError, match="confirmed tutor session requires a problem_text"):
        VisualTutorSessionCreateRequest(
            user_id="student-1",
            session_mode="confirmed_problem",
            subject="Mathematics",
        )
