from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routes.curriculum import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_curriculum_retrieve_get_valid_retrieval() -> None:
    app = _make_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/curriculum/retrieve",
            params={
                "grade": 10,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "problem_type": "linear_equation_one_variable",
                "message": "Solve 2x + 5 = 15",
                "language": "en",
                "max_results": 2,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "math.g10.linear_equations.one_variable" in data["curriculum_chunk_ids"]
    assert "ax + b = c" in data["formulas"]
    assert data["confidence"] > 0
    assert data["metadata"]["retriever"] == "visual_tutor_curriculum_retriever_v1"


@pytest.mark.asyncio
async def test_curriculum_retrieve_post_valid_retrieval() -> None:
    app = _make_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/curriculum/retrieve",
            json={
                "grade": 10,
                "subject": "Mathematics",
                "topic": "Equation of a Line",
                "problem_type": "line_through_two_points",
                "message": "Find the equation of the line through D(0,1) and E(1,3)",
                "language": "en",
                "max_results": 1,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["curriculum_chunk_ids"] == [
        "math.g10.coordinate_geometry.line_equation"
    ]
    assert "y = mx + b" in data["formulas"]
    # Only a safe reference is public; raw authoring sources stay internal.
    source = data["curriculum_sources"][0]
    assert source["curriculum_chunk_id"] == "math.g10.coordinate_geometry.line_equation"
    assert "source" not in source and "internal_admin_note" not in source


@pytest.mark.asyncio
async def test_curriculum_retrieve_unknown_topic_returns_empty_result() -> None:
    app = _make_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/curriculum/retrieve",
            params={
                "grade": 12,
                "subject": "Mathematics",
                "topic": "Unknown Topic",
                "problem_type": "unknown_problem",
                "message": "This topic is not in seed data",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["chunks"] == []
    assert data["curriculum_chunk_ids"] == []
    assert data["confidence"] == 0
