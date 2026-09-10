from __future__ import annotations

import json
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient

from api.models.curriculum_cambodia import CurriculumGraph, RichProblem
from api.services.curriculum_service import CurriculumService
from scripts.seed_curriculum import build_units


@pytest.fixture()
def seeded_records():
    payload = json.loads(
        (Path(__file__).parents[1] / "data" / "cambodia_curriculum.json").read_text(
            encoding="utf-8"
        )
    )
    return build_units(payload)


def test_grade_10_seed_has_15_units_and_42_topics(seeded_records) -> None:
    units, problems = seeded_records
    topics = [topic for unit in units for topic in unit.topics]
    assert len(units) == 15
    assert len(topics) == 42
    assert len(problems) == 126
    assert all(len(topic.example_problems) == 3 for topic in topics)
    outcomes = [outcome.code for topic in topics for outcome in topic.learning_outcomes]
    assert len(outcomes) == len(set(outcomes))


def test_each_subject_graph_is_a_dag(seeded_records) -> None:
    units, _ = seeded_records
    for subject in {unit.subject for unit in units}:
        topics = [
            topic for unit in units if unit.subject == subject for topic in unit.topics
        ]
        graph = CurriculumGraph(
            subject=subject,
            grade=10,
            topics={topic.topic_id: topic for topic in topics},
            edges={topic.topic_id: topic.prerequisites for topic in topics},
        )
        assert graph.get_path(topics[0].topic_id, topics[-1].topic_id)


@pytest.mark.asyncio
async def test_curriculum_service_queries_topics_dependencies_and_problems(
    seeded_records,
) -> None:
    units, problems = seeded_records
    database = AsyncMongoMockClient().reanai
    topics = [topic for unit in units for topic in unit.topics]
    await database.curriculum_topics.insert_many(
        [topic.model_dump(mode="json") for topic in topics]
    )
    await database.rich_problems.insert_many(
        [problem.model_dump(mode="json") for problem in problems]
    )
    math_topics = [topic for topic in topics if topic.subject == "math"]
    graph = CurriculumGraph(
        subject="math",
        grade=10,
        topics={topic.topic_id: topic for topic in math_topics},
        edges={topic.topic_id: topic.prerequisites for topic in math_topics},
    )
    await database.curriculum_graphs.insert_one(graph.model_dump(mode="json"))
    service = CurriculumService(database)
    topic = await service.get_topic("math_g10_linear_eq_02")
    assert topic.name == "One-variable equations"
    assert [
        item.topic_id for item in await service.get_prerequisites(topic.topic_id)
    ] == ["math_g10_linear_eq_01"]
    assert len(await service.get_next_topics("math_g10_linear_eq_01")) == 1
    assert len(await service.get_learning_outcomes(topic.topic_id)) == 1
    related = await service.find_related_problems(topic.topic_id)
    assert all(isinstance(problem, RichProblem) for problem in related)
    assert len(related) == 3
