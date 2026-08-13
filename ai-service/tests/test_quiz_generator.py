from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.models.quiz import QuizGenerationRequest, QuizGenerationResponse
from api.routes.quiz import router
from api.services.quiz_generator import clear_quiz_cache, generate_topic_quiz


class FakeQuizLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return json.dumps(self.payload)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def setup_function() -> None:
    clear_quiz_cache()


def test_generate_linear_equation_quiz() -> None:
    response = generate_topic_quiz(
        QuizGenerationRequest(
            subject="Mathematics",
            topic="Linear Equations",
            problem_type="linear_equation_one_variable",
            difficulty="easy",
        )
    )

    assert response.subject == "Mathematics"
    assert response.topic == "Linear Equations"
    assert response.problem_type == "linear_equation_one_variable"
    assert response.verified is True
    assert 3 <= len(response.questions) <= 5
    assert response.questions[0].question_text.startswith("Solve:")
    assert response.questions[0].correct_answer == "A"
    assert response.questions[0].metadata["verified_by"] == "sympy"


def test_quiz_schema_validation_round_trip() -> None:
    response = generate_topic_quiz(QuizGenerationRequest())
    payload = response.model_dump(mode="json")

    parsed = QuizGenerationResponse.model_validate(payload)

    assert parsed.quiz_id == response.quiz_id
    assert len(parsed.questions) == 3
    assert parsed.metadata["generator"] == "basic_verified_quiz_generator_v1"


def test_correct_answer_is_sympy_verified() -> None:
    response = generate_topic_quiz(QuizGenerationRequest(topic="Linear Equations"))
    question = response.questions[0]

    assert response.verified is True
    assert "=" in question.metadata["equation"]
    assert question.metadata["sympy_solution"] == question.expected_answer


def test_generation_is_not_an_in_memory_persistence_layer() -> None:
    request = QuizGenerationRequest(
        subject="Mathematics",
        topic="Linear Equations",
        difficulty="easy",
    )

    first = generate_topic_quiz(request)
    second = generate_topic_quiz(request)

    assert first.cache_hit is False
    assert second.cache_hit is False
    assert second.quiz_id == first.quiz_id
    assert second.questions[0].expected_answer == first.questions[0].expected_answer


def test_invalid_llm_generated_answer_is_rejected_and_falls_back() -> None:
    invalid_payload = {
        "quiz_id": "quiz-bad",
        "subject": "Mathematics",
        "topic": "Linear Equations",
        "problem_type": "linear_equation_one_variable",
        "difficulty": "easy",
        "questions": [
            {
                "id": "bad-q1",
                "type": "multiple_choice",
                "question_text": "Solve 2x + 5 = 15",
                "choices": [
                    {"id": "A", "text": "x = 4"},
                    {"id": "B", "text": "x = 6"},
                ],
                "expected_answer": "x = 4",
                "correct_answer": "A",
                "explanation": "Wrong generated explanation.",
                "difficulty": "easy",
                "topic": "Linear Equations",
                "problem_type": "linear_equation_one_variable",
                "metadata": {"equation": "2x + 5 = 15"},
            }
        ],
        "verified": True,
        "cache_hit": False,
        "metadata": {"source": "fake_llm"},
    }
    fake_llm = FakeQuizLLMClient(invalid_payload)

    response = generate_topic_quiz(
        QuizGenerationRequest(topic="Linear Equations", use_llm=True),
        llm_client=fake_llm,
    )

    assert fake_llm.calls
    assert response.metadata["source"] == "deterministic_fallback"
    assert response.verified is True
    assert len(response.questions) == 3


@pytest.mark.asyncio
async def test_generate_quiz_endpoint_requires_internal_auth_and_returns_private_schema(monkeypatch) -> None:
    app = _make_app()
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-internal-token")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/quiz/generate",
            json={
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "problem_type": "linear_equation_one_variable",
            },
            headers={
                "x-visual-tutor-user-id": "student-1",
                "x-visual-tutor-internal-token": "test-internal-token",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert len(data["questions"]) == 3
    # This private response is available only to the trusted backend, which strips keys for Flutter.
    assert data["questions"][0]["correct_answer"] == "A"


def test_personalization_uses_hints_and_supported_types() -> None:
    response = generate_topic_quiz(QuizGenerationRequest(
        topic="Slope", problem_type="slope_from_points", hint_count=3,
        skill_tags=["rise-over-run"], verification_results=["invalid"],
    ))

    assert len(response.questions) == 3
    assert response.metadata["personalization"]["recommended_difficulty"] == "beginner"
    assert all(question.problem_type == "slope_from_points" for question in response.questions)


def test_unsupported_generated_practice_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported targeted-practice"):
        generate_topic_quiz(QuizGenerationRequest(problem_type="geometry_proof"))
