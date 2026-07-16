from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.misconception import MisconceptionLog
from app.models.progress import Streak
from app.models.tutor import (
    TutorGuidedAttempt,
    TutorGuidedStep,
    TutorQuizAnswer,
    TutorQuizAttempt,
)
from app.models.user import User

router = APIRouter(prefix="/tutor", tags=["Tutor"])


class GuidedAttemptCreate(BaseModel):
    subject_id: str
    subject_title: str
    topic_id: str
    topic_title: str
    problem_prompt: str


class GuidedStepCreate(BaseModel):
    step_index: int = Field(ge=0)
    student_answer: str = ""
    expected_step: str = ""
    feedback: str = ""
    is_correct: bool = False
    hint_requested: bool = False
    complete_attempt: bool = False


class QuizAttemptCreate(BaseModel):
    subject_id: str
    subject_title: str
    topic_id: str
    topic_title: str
    total_questions: int = Field(default=0, ge=0)


class QuizAnswerCreate(BaseModel):
    question_index: int = Field(ge=0)
    question: str
    selected_index: int | None = None
    correct_index: int
    is_correct: bool
    explanation: str = ""


class QuizAttemptComplete(BaseModel):
    score: int = Field(ge=0)
    correct_count: int = Field(ge=0)


_CATALOG: list[dict[str, Any]] = [
    {
        "id": "math",
        "title": "Mathematics",
        "icon": "calculate",
        "color": "#2563EB",
        "description": "Step-by-step problem solving and practice.",
        "topics": [
            {
                "id": "linear_equations",
                "title": "Linear Equations",
                "subtitle": "Solving one-variable equations",
                "progress": 0.65,
                "guided_problem": {
                    "prompt": "Solve: 2x + 5 = 15",
                    "coach_intro": "Let's isolate x one step at a time.",
                    "expected_next_step": "Subtract 5 from both sides",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Subtract 5 from both sides to isolate the term with x.",
                            "hint": "What operation undoes +5?",
                        },
                        {
                            "title": "Step 2",
                            "explanation": "Now divide both sides by 2 to solve for x.",
                            "hint": "Once you have 2x = 10, what should you do next?",
                        },
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "Solve 5x + 3 = 18.",
                        "options": ["x = 3", "x = 4", "x = 5", "x = 15"],
                        "correct_index": 0,
                        "explanation": "Subtract 3 to get 5x = 15, then divide by 5.",
                    }
                ],
            },
            {
                "id": "geometry",
                "title": "Geometry",
                "subtitle": "Triangles, circles, and theorems",
                "progress": 0.40,
                "guided_problem": {
                    "prompt": "Find the area of a triangle with base 8 cm and height 5 cm.",
                    "coach_intro": "Use the area formula for triangles.",
                    "expected_next_step": "Multiply the base and height",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Recall the formula: Area = 1/2 × base × height.",
                            "hint": "What values are base and height here?",
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "What is the area of a triangle with base 10 and height 6?",
                        "options": ["16", "30", "60", "20"],
                        "correct_index": 1,
                        "explanation": "Area = 1/2 × 10 × 6 = 30.",
                    }
                ],
            },
            {
                "id": "functions",
                "title": "Functions",
                "subtitle": "Relations and mappings",
                "progress": 0.25,
                "guided_problem": {
                    "prompt": "Evaluate f(x) = 2x + 1 when x = 4.",
                    "coach_intro": "We only need substitution.",
                    "expected_next_step": "Replace x with 4",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Substitute x = 4 into 2x + 1.",
                            "hint": "What expression do you get after substitution?",
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "If f(x) = x + 7, what is f(3)?",
                        "options": ["4", "7", "10", "21"],
                        "correct_index": 2,
                        "explanation": "Replace x with 3: 3 + 7 = 10.",
                    }
                ],
            },
            {
                "id": "trigonometry",
                "title": "Trigonometry",
                "subtitle": "Angles and trigonometric ratios",
                "progress": 0.10,
                "guided_problem": {
                    "prompt": "If opposite = 3 and hypotenuse = 5, find sin θ.",
                    "coach_intro": "Use the sine ratio.",
                    "expected_next_step": "Write opposite / hypotenuse",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Recall sin θ = opposite / hypotenuse.",
                            "hint": "Which two sides do you need?",
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "sin θ equals which ratio in a right triangle?",
                        "options": [
                            "adjacent / hypotenuse",
                            "opposite / adjacent",
                            "opposite / hypotenuse",
                            "hypotenuse / opposite",
                        ],
                        "correct_index": 2,
                        "explanation": "Sine compares the opposite side with the hypotenuse.",
                    }
                ],
            },
        ],
    },
    {
        "id": "physics",
        "title": "Physics",
        "icon": "science",
        "color": "#0F766E",
        "description": "Conceptual explanations with applied problem solving.",
        "topics": [
            {
                "id": "motion",
                "title": "Motion",
                "subtitle": "Distance, speed, and time",
                "progress": 0.52,
                "guided_problem": {
                    "prompt": "A car travels 120 km in 2 hours. Find its speed.",
                    "coach_intro": "Use the speed formula.",
                    "expected_next_step": "Divide distance by time",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Recall speed = distance ÷ time.",
                            "hint": "What is the distance? What is the time?",
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "If distance is 150 m and time is 10 s, what is speed?",
                        "options": ["15 m/s", "1500 m/s", "140 m/s", "16 m/s"],
                        "correct_index": 0,
                        "explanation": "Speed = 150 ÷ 10 = 15 m/s.",
                    }
                ],
            },
            {
                "id": "forces",
                "title": "Forces",
                "subtitle": "Newton's laws and net force",
                "progress": 0.33,
                "guided_problem": {
                    "prompt": "A 2 kg object accelerates at 3 m/s². Find the force.",
                    "coach_intro": "This is a direct F = ma problem.",
                    "expected_next_step": "Multiply mass by acceleration",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Use Newton's second law: F = m × a.",
                            "hint": "Which values represent mass and acceleration?",
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "What is the net force on a 4 kg object accelerating at 2 m/s²?",
                        "options": ["2 N", "6 N", "8 N", "12 N"],
                        "correct_index": 2,
                        "explanation": "F = ma = 4 × 2 = 8 N.",
                    }
                ],
            },
        ],
    },
    {
        "id": "english",
        "title": "English",
        "icon": "menu_book",
        "color": "#0891B2",
        "description": "Grammar, vocabulary, reading, and writing practice.",
        "topics": [
            {
                "id": "grammar",
                "title": "Grammar",
                "subtitle": "Sentence structure and accuracy",
                "progress": 0.58,
                "guided_problem": {
                    "prompt": 'Correct this sentence: "She go to school every day."',
                    "coach_intro": "Think about subject-verb agreement.",
                    "expected_next_step": 'Change "go" to "goes"',
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": 'The subject "She" takes a singular verb in present simple.',
                            "hint": 'What verb form matches "she"?',
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": "Choose the correct sentence.",
                        "options": [
                            "He go to work at 8.",
                            "He goes to work at 8.",
                            "He going to work at 8.",
                            "He gone to work at 8.",
                        ],
                        "correct_index": 1,
                        "explanation": "Third-person singular uses goes in present simple.",
                    }
                ],
            },
            {
                "id": "vocabulary",
                "title": "Vocabulary",
                "subtitle": "Word meaning and usage",
                "progress": 0.42,
                "guided_problem": {
                    "prompt": 'Use the word "curious" in a sentence.',
                    "coach_intro": "Show the meaning through context.",
                    "expected_next_step": "Write a sentence that shows interest or wanting to know",
                    "steps": [
                        {
                            "title": "Step 1",
                            "explanation": "Curious describes someone who wants to know more.",
                            "hint": "Think of a student asking many questions.",
                        }
                    ],
                },
                "quiz_questions": [
                    {
                        "question": 'Which word is closest in meaning to "curious"?',
                        "options": ["bored", "interested", "angry", "silent"],
                        "correct_index": 1,
                        "explanation": "Curious means interested and eager to learn.",
                    }
                ],
            },
        ],
    },
]


def _catalog_topics() -> list[dict[str, Any]]:
    return [
        {**topic, "subject_id": subject["id"], "subject_title": subject["title"], "subject_color": subject["color"]}
        for subject in _CATALOG
        for topic in subject["topics"]
    ]


def _topic_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    return {(topic["subject_id"], topic["id"]): topic for topic in _catalog_topics()}


def _format_percent(value: float) -> str:
    return f"{round(value * 100)}%"


async def _topic_mastery(db: AsyncSession, user_id: uuid.UUID) -> dict[tuple[str, str], float]:
    quiz_rows = await db.execute(
        select(
            TutorQuizAttempt.subject_id,
            TutorQuizAttempt.topic_id,
            func.avg(TutorQuizAttempt.score).label("avg_score"),
        )
        .where(TutorQuizAttempt.user_id == user_id, TutorQuizAttempt.status == "completed")
        .group_by(TutorQuizAttempt.subject_id, TutorQuizAttempt.topic_id)
    )
    mastery: dict[tuple[str, str], float] = {
        (row.subject_id, row.topic_id): float(row.avg_score or 0) / 100
        for row in quiz_rows.all()
    }

    guided_rows = await db.execute(
        select(
            TutorGuidedAttempt.subject_id,
            TutorGuidedAttempt.topic_id,
            func.count(TutorGuidedAttempt.id).label("completed_count"),
        )
        .where(
            TutorGuidedAttempt.user_id == user_id,
            TutorGuidedAttempt.status == "completed",
        )
        .group_by(TutorGuidedAttempt.subject_id, TutorGuidedAttempt.topic_id)
    )
    for row in guided_rows.all():
        key = (row.subject_id, row.topic_id)
        guided_progress = min(1.0, float(row.completed_count or 0) * 0.2)
        mastery[key] = max(mastery.get(key, 0.0), guided_progress)
    return mastery


async def _recent_mistakes(db: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    quiz_mistakes = await db.execute(
        select(TutorQuizAnswer, TutorQuizAttempt)
        .join(TutorQuizAttempt, TutorQuizAnswer.attempt_id == TutorQuizAttempt.id)
        .where(TutorQuizAttempt.user_id == user_id, TutorQuizAnswer.is_correct.is_(False))
        .order_by(TutorQuizAnswer.created_at.desc())
        .limit(5)
    )
    mistakes = [
        {
            "title": attempt.topic_title,
            "detail": answer.explanation or answer.question,
            "subject": attempt.subject_title,
            "created_at": answer.created_at.isoformat(),
        }
        for answer, attempt in quiz_mistakes.all()
    ]
    if mistakes:
        return mistakes

    misconception_rows = await db.execute(
        select(MisconceptionLog)
        .where(MisconceptionLog.user_id == user_id)
        .order_by(MisconceptionLog.created_at.desc())
        .limit(5)
    )
    return [
        {
            "title": row.error_pattern,
            "detail": row.sub_topic,
            "subject": row.subject,
            "created_at": row.created_at.isoformat(),
        }
        for row in misconception_rows.scalars().all()
    ]


@router.get("/subjects")
async def list_subjects(current_user: User = Depends(get_current_user)):
    return {"subjects": _CATALOG}


@router.get("/subjects/{subject_id}/topics")
async def list_subject_topics(subject_id: str, current_user: User = Depends(get_current_user)):
    for subject in _CATALOG:
        if subject["id"] == subject_id:
            return {"subject": subject}
    return {"subject": None, "topics": []}


@router.get("/dashboard")
async def get_tutor_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    streak_result = await db.execute(
        select(Streak.current_streak).where(Streak.user_id == current_user.id)
    )
    streak_days = streak_result.scalar() or 0

    mastery = await _topic_mastery(db, current_user.id)
    topics_by_key = _topic_lookup()

    weak_result = await db.execute(
        select(
            MisconceptionLog.subject,
            MisconceptionLog.sub_topic,
            func.count(MisconceptionLog.id).label("error_count"),
        )
        .where(MisconceptionLog.user_id == current_user.id)
        .group_by(MisconceptionLog.subject, MisconceptionLog.sub_topic)
        .order_by(func.count(MisconceptionLog.id).desc())
        .limit(3)
    )
    weak_topics: list[dict[str, Any]] = [
        {
            "subject": row.subject,
            "title": row.sub_topic,
            "error_count": row.error_count,
            "progress": 0.0,
        }
        for row in weak_result.all()
    ]

    if not weak_topics:
        scored_topics = sorted(
            (
                (key, topics_by_key[key], mastery.get(key, float(topics_by_key[key].get("progress", 0.0))))
                for key in topics_by_key
            ),
            key=lambda item: item[2],
        )
        weak_topics = [
            {
                "subject": topic["subject_title"],
                "title": topic["title"],
                "error_count": 0,
                "progress": progress,
            }
            for _, topic, progress in scored_topics[:3]
        ]

    total_topics = len(topics_by_key) or 1
    completion_percentage = int(
        round(sum(mastery.get(key, 0.0) for key in topics_by_key) / total_topics * 100)
    )

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    completed_guided_today = await db.scalar(
        select(func.count(TutorGuidedAttempt.id)).where(
            TutorGuidedAttempt.user_id == current_user.id,
            TutorGuidedAttempt.status == "completed",
            TutorGuidedAttempt.completed_at >= today_start,
        )
    )
    completed_quizzes_today = await db.scalar(
        select(func.count(TutorQuizAttempt.id)).where(
            TutorQuizAttempt.user_id == current_user.id,
            TutorQuizAttempt.status == "completed",
            TutorQuizAttempt.completed_at >= today_start,
        )
    )

    latest_attempt = await db.scalar(
        select(TutorGuidedAttempt)
        .where(TutorGuidedAttempt.user_id == current_user.id)
        .order_by(TutorGuidedAttempt.updated_at.desc())
        .limit(1)
    )
    if latest_attempt:
        continue_learning = {
            "subject": latest_attempt.subject_title,
            "topic": latest_attempt.topic_title,
            "progress": mastery.get((latest_attempt.subject_id, latest_attempt.topic_id), 0.0),
        }
    else:
        topic = _CATALOG[0]["topics"][0]
        continue_learning = {
            "subject": _CATALOG[0]["title"],
            "topic": topic["title"],
            "progress": mastery.get(("math", topic["id"]), float(topic["progress"])),
        }

    trend_rows = await db.execute(
        select(TutorQuizAttempt.completed_at, TutorQuizAttempt.score)
        .where(
            TutorQuizAttempt.user_id == current_user.id,
            TutorQuizAttempt.status == "completed",
            TutorQuizAttempt.completed_at.is_not(None),
        )
        .order_by(TutorQuizAttempt.completed_at.desc())
        .limit(5)
    )
    score_trend = [
        {
            "label": row.completed_at.strftime("%b %-d") if row.completed_at else "Recent",
            "value": float(row.score or 0) / 100,
        }
        for row in reversed(trend_rows.all())
    ]
    recent_mistakes = await _recent_mistakes(db, current_user.id)
    recommendation = weak_topics[0] if weak_topics else {
        "subject": "Mathematics",
        "title": "Linear Equations",
        "progress": 0.0,
    }

    return {
        "student_name": getattr(current_user, "full_name", None)
        or getattr(current_user, "username", None)
        or getattr(current_user, "email", "Student").split("@")[0],
        "streak_days": streak_days,
        "today_goal": {"completed": int(completed_guided_today or 0) + int(completed_quizzes_today or 0), "target": 3},
        "continue_learning": continue_learning,
        "weak_topics": weak_topics,
        "recommendation": {
            "subject": recommendation["subject"],
            "topic": recommendation["title"],
            "minutes": 15,
        },
        "completion_percentage": completion_percentage,
        "score_trend": score_trend,
        "recent_mistakes": recent_mistakes,
    }


@router.post("/guided-attempts")
async def create_guided_attempt(
    payload: GuidedAttemptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = TutorGuidedAttempt(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        subject_title=payload.subject_title,
        topic_id=payload.topic_id,
        topic_title=payload.topic_title,
        problem_prompt=payload.problem_prompt,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return {"id": str(attempt.id), "status": attempt.status}


@router.post("/guided-attempts/{attempt_id}/steps")
async def record_guided_step(
    attempt_id: uuid.UUID,
    payload: GuidedStepCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await db.scalar(
        select(TutorGuidedAttempt).where(
            TutorGuidedAttempt.id == attempt_id,
            TutorGuidedAttempt.user_id == current_user.id,
        )
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Guided attempt not found")

    step = TutorGuidedStep(
        attempt_id=attempt.id,
        step_index=payload.step_index,
        student_answer=payload.student_answer,
        expected_step=payload.expected_step,
        feedback=payload.feedback,
        is_correct=payload.is_correct,
        hint_requested=payload.hint_requested,
    )
    db.add(step)
    if payload.hint_requested:
        attempt.hints_requested += 1
    elif payload.is_correct:
        attempt.steps_completed = max(attempt.steps_completed, payload.step_index + 1)
    if payload.complete_attempt:
        attempt.status = "completed"
        attempt.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "id": str(step.id),
        "attempt_status": attempt.status,
        "hints_requested": attempt.hints_requested,
        "steps_completed": attempt.steps_completed,
    }


@router.post("/quiz-attempts")
async def create_quiz_attempt(
    payload: QuizAttemptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = TutorQuizAttempt(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        subject_title=payload.subject_title,
        topic_id=payload.topic_id,
        topic_title=payload.topic_title,
        total_questions=payload.total_questions,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return {"id": str(attempt.id), "status": attempt.status}


@router.post("/quiz-attempts/{attempt_id}/answers")
async def record_quiz_answer(
    attempt_id: uuid.UUID,
    payload: QuizAnswerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await db.scalar(
        select(TutorQuizAttempt).where(
            TutorQuizAttempt.id == attempt_id,
            TutorQuizAttempt.user_id == current_user.id,
        )
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    answer = TutorQuizAnswer(
        attempt_id=attempt.id,
        question_index=payload.question_index,
        question=payload.question,
        selected_index=payload.selected_index,
        correct_index=payload.correct_index,
        is_correct=payload.is_correct,
        explanation=payload.explanation,
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)
    return {"id": str(answer.id)}


@router.post("/quiz-attempts/{attempt_id}/complete")
async def complete_quiz_attempt(
    attempt_id: uuid.UUID,
    payload: QuizAttemptComplete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await db.scalar(
        select(TutorQuizAttempt).where(
            TutorQuizAttempt.id == attempt_id,
            TutorQuizAttempt.user_id == current_user.id,
        )
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    attempt.score = payload.score
    attempt.correct_count = payload.correct_count
    attempt.status = "completed"
    attempt.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(attempt.id), "status": attempt.status, "score": attempt.score}
