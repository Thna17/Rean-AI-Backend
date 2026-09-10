"""Validate and idempotently seed structured Cambodia Grade 10 curriculum data."""

from __future__ import annotations
import asyncio, json, os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient
from api.models.curriculum_cambodia import (
    CurriculumGraph,
    CurriculumUnit,
    LearningOutcome,
    RichProblem,
    Topic,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "cambodia_curriculum.json"


def build_units(
    payload: dict[str, object],
) -> tuple[list[CurriculumUnit], list[RichProblem]]:
    """Expand compact authored topics into fully validated records and sample IDs."""
    units: list[CurriculumUnit] = []
    problems: list[RichProblem] = []
    previous_unit_terminal: dict[str, str] = {}
    for raw_unit in payload["units"]:  # type: ignore[index]
        unit = dict(raw_unit)  # type: ignore[arg-type]
        topics: list[Topic] = []
        previous: str | None = previous_unit_terminal.get(unit["subject"])
        for number, (topic_id, name, name_khmer) in enumerate(unit.pop("topics"), 1):
            outcome = LearningOutcome(
                code=f"LOCAL-{unit['subject'].upper()}-G{unit['grade']}-{topic_id.upper()}",
                description=f"Apply {name.lower()} in guided Grade 10 problems.",
                description_khmer=f"អនុវត្ត {name_khmer} ក្នុងលំហាត់ណែនាំថ្នាក់ទី១០។",
                grade=unit["grade"],
                subject=unit["subject"],
                source=str(payload["source"]),
            )
            examples = [f"{topic_id}_p{index:02}" for index in range(1, 4)]
            topic = Topic(
                topic_id=topic_id,
                subject=unit["subject"],
                grade=unit["grade"],
                unit_name=unit["name"],
                name=name,
                name_khmer=name_khmer,
                concepts=[topic_id.removeprefix(f"{unit['subject']}_g10_")],
                prerequisites=[previous] if previous else [],
                learning_outcomes=[outcome],
                example_problems=examples,
            )
            topics.append(topic)
            problems.extend(
                RichProblem(
                    problem_id=item,
                    subject=topic.subject,
                    grade=topic.grade,
                    unit=topic.unit_name,
                    topic_id=topic.topic_id,
                    problem_text=f"Guided problem: {topic.name}",
                    problem_text_khmer=f"លំហាត់ណែនាំ៖ {topic.name_khmer}",
                    problem_type="guided_visual",
                    visualizations_needed=["diagram"],
                    concepts=topic.concepts,
                    prerequisites=topic.prerequisites,
                )
                for item in examples
            )
            previous = topic_id
        units.append(CurriculumUnit(**unit, topics=topics))
        previous_unit_terminal[unit["subject"]] = topics[-1].topic_id
    return units, problems


async def seed() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    units, problems = build_units(payload)
    client = AsyncIOMotorClient(
        os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    )
    database = client[os.environ.get("MONGODB_DATABASE", "reanai")]
    topics = [topic for unit in units for topic in unit.topics]
    groups: dict[tuple[str, int], list[Topic]] = {}
    for topic in topics:
        groups.setdefault((topic.subject, topic.grade), []).append(topic)
    graphs = [
        CurriculumGraph(
            subject=subject,
            grade=grade,
            topics={topic.topic_id: topic for topic in grouped},
            edges={topic.topic_id: topic.prerequisites for topic in grouped},
        )
        for (subject, grade), grouped in groups.items()
    ]
    for graph in graphs:
        await database.curriculum_graphs.replace_one(
            {"subject": graph.subject, "grade": graph.grade},
            graph.model_dump(mode="json"),
            upsert=True,
        )
    for topic in topics:
        await database.curriculum_topics.replace_one(
            {"topic_id": topic.topic_id}, topic.model_dump(mode="json"), upsert=True
        )
    for problem in problems:
        await database.rich_problems.replace_one(
            {"problem_id": problem.problem_id},
            problem.model_dump(mode="json"),
            upsert=True,
        )
    print(
        f"Loaded {len(topics)} topics, {len(problems)} problems, {sum(len(topic.learning_outcomes) for topic in topics)} learning outcomes"
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
