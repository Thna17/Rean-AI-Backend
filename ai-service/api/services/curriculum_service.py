"""Mongo-backed queries for the structured Cambodia curriculum."""

from __future__ import annotations
from typing import Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from api.models.curriculum_cambodia import (
    CurriculumGraph,
    LearningOutcome,
    RichProblem,
    Topic,
)


class CurriculumService:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._database = database

    async def load_curriculum(self, subject: str, grade: str | int) -> CurriculumGraph:
        document = await self._database.curriculum_graphs.find_one(
            {"subject": subject, "grade": int(grade)}, {"_id": 0}
        )
        if document is None:
            raise LookupError(f"No curriculum graph for {subject} grade {grade}")
        return CurriculumGraph.model_validate(document)

    async def get_topic(self, topic_id: str) -> Topic:
        document = await self._database.curriculum_topics.find_one(
            {"topic_id": topic_id}, {"_id": 0}
        )
        if document is None:
            raise LookupError(f"Unknown topic: {topic_id}")
        return Topic.model_validate(document)

    async def get_prerequisites(self, topic_id: str) -> list[Topic]:
        topic = await self.get_topic(topic_id)
        return [await self.get_topic(item) for item in topic.prerequisites]

    async def get_next_topics(self, topic_id: str) -> list[Topic]:
        cursor = self._database.curriculum_topics.find(
            {"prerequisites": topic_id}, {"_id": 0}
        )
        return [Topic.model_validate(item) async for item in cursor]

    async def get_learning_outcomes(self, topic_id: str) -> list[LearningOutcome]:
        return (await self.get_topic(topic_id)).learning_outcomes

    async def find_related_problems(self, topic_id: str) -> list[RichProblem]:
        cursor = self._database.rich_problems.find({"topic_id": topic_id}, {"_id": 0})
        return [RichProblem.model_validate(item) async for item in cursor]
