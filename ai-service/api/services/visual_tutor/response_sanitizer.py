from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterable, Optional

from api.models.visual_tutor import (
    CanvasElement,
    BoardHistoryEntry,
    TeachingBoardAction,
    TeachingBoardActionType,
    TeachingBoardElement,
    TeachingBoardState,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorCanvasState,
    VisualTutorInteraction,
    VisualTutorInteractionChoice,
    VisualTutorNextStudentAction,
    VisualTutorSpeech,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.policy import VisualTutorPolicyDecision
from api.services.visual_tutor.board_contract import validate_board_response

SANITIZER_VERSION = "visual_tutor_final_answer_sanitizer_v1"
LOCKED_ANSWER_TEXT = "Final answer is locked."
LOCKED_TEXT_REPLACEMENT = "Final answer is locked for now."

# ── Answer-leak detection patterns ──────────────────────────────────────────
# These patterns are intentionally broad to catch LLM rephrasing. The
# _answer_phrase_replacement guard re-allows pedagogically safe uses.
_ANSWER_PHRASE_RE = re.compile(
    r"\bfinal\s+answer\s*(?:is|:)\s*[^.\nប!?]+"
    r"|(?<!partial\s)\b(?:answer|solution|solutions|roots?|result|value)\s*"
    r"(?:is|are|:)\s*[^.\nប!?]+"
    r"|(?<!partial\s)\banswer\s+[a-zA-Z]\s*=\s*[^.\nប!?]+"
    # 'So x = 5' / 'Therefore x = 5' / 'Thus x = 5'
    r"|\b(?:so|therefore|thus|hence)\s+[a-zA-Z]\s*=\s*[-+]?[\d.]+"
    # 'x equals 5' / 'x is equal to 5'
    r"|\b[a-zA-Z]\s+(?:equals?|is\s+equal\s+to)\s+[-+]?[\d.]+"
    # Khmer answer leaks: ចម័យមាន / ចំលើយជាប + assignment
    r"|ចំម័យមាន[^\.\nប!?]*[a-zA-Z]\s*=\s*[-+]?[\d.]+"
    r"|ចំលើយជាប[^\.\nប!?]*[a-zA-Z]\s*=\s*[-+]?[\d.]+"
    # Bare numerical assignment at sentence start: 'x = 5' or 'x = -3/2'
    r"|^\s*[a-zA-Z]\s*=\s*[-+]?[\d./]+(?:\s*[-+*/]\s*[\d./]+)*\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_COPY_ASSIGNMENT_RE = re.compile(r"(?i)\bcopy\b[^.\nប!?]*[a-zA-Z]\s*=\s*[^.\nប!?]+")
_ANSWER_ASSIGNMENT_RE = re.compile(
    r"\b[a-zA-Z]\s*=\s*[-+]?\d+(?:\.\d+)?(?:/\d+)?"
    r"(?:\s*[-+*/]\s*[a-zA-Z0-9().]+)*\b"
)
# Scoped per sanitize call (the ~15 private helpers below stay pure-signature)
# so one request's given values can never exempt text in another request.
_GIVEN_VALUES: ContextVar[frozenset[str]] = ContextVar(
    "visual_tutor_given_values", default=frozenset()
)
_ASSIGNED_NUMBER_RE = re.compile(r"\b[a-zA-Z]\s*=\s*([-+]?\d+(?:\.\d+)?)")
# Board action types that structurally reveal the answer — must be blocked.
_STRUCTURAL_ANSWER_ACTION_TYPES = frozenset({
    "final_answer_reveal",
    "reveal_answer",
})


@dataclass
class _SanitizationChanges:
    fields: set[str] = field(default_factory=set)
    board_item_indices: set[int] = field(default_factory=set)
    canvas_element_ids: set[str] = field(default_factory=set)
    canvas_action_ids: set[str] = field(default_factory=set)
    board_action_ids: set[str] = field(default_factory=set)
    teaching_board_element_ids: set[str] = field(default_factory=set)
    teaching_board_action_ids: set[str] = field(default_factory=set)

    @property
    def changed(self) -> bool:
        return bool(
            self.fields
            or self.board_item_indices
            or self.canvas_element_ids
            or self.canvas_action_ids
            or self.board_action_ids
            or self.teaching_board_element_ids
            or self.teaching_board_action_ids
        )


def sanitize_visual_tutor_response(
    response: VisualTutorTurnResponse,
    *,
    policy: Optional[VisualTutorPolicyDecision] = None,
    given_values: Iterable[str] = (),
) -> VisualTutorTurnResponse:
    """Remove final-answer leaks from visible tutor response fields while locked.

    `given_values` are numbers the student's own problem supplies (e.g. a
    limit's approach point); restating one is not treated as a leak.
    """
    token = _GIVEN_VALUES.set(
        frozenset(_normalize_number(value) for value in given_values if value)
    )
    try:
        return _sanitize_locked_response(response, policy)
    finally:
        _GIVEN_VALUES.reset(token)


def _sanitize_locked_response(
    response: VisualTutorTurnResponse,
    policy: Optional[VisualTutorPolicyDecision],
) -> VisualTutorTurnResponse:
    if not _should_lock_final_answer(response, policy):
        return validate_board_response(response)

    changes = _SanitizationChanges()
    spoken_text = _sanitize_text(response.spoken_text)
    if spoken_text != response.spoken_text:
        changes.fields.add("spoken_text")

    display_text = _sanitize_text(response.display_text)
    if display_text != response.display_text:
        changes.fields.add("display_text")

    student_task = _sanitize_visible_text(response.student_task)
    if student_task != response.student_task:
        changes.fields.add("student_task")

    board = _sanitize_board(response.board, changes)
    canvas = _sanitize_canvas_state(response.canvas, changes)
    canvas_actions = _sanitize_canvas_actions(response.canvas_actions, changes)
    speech = _sanitize_speech(response.speech, changes)
    board_actions = _sanitize_board_actions(response.board_actions, changes)
    teaching_board = _sanitize_teaching_board(response.teaching_board, changes)
    teaching_board_history = _sanitize_board_history(
        response.teaching_board_history,
        changes,
    )
    interaction = _sanitize_interaction(response.interaction, changes)
    next_student_action = _sanitize_next_student_action(
        response.next_student_action,
        changes,
    )
    response_metadata = _sanitize_metadata(response.metadata)
    if response_metadata != response.metadata:
        changes.fields.add("metadata")

    if not changes.changed:
        return validate_board_response(response)

    metadata = {
        **response_metadata,
        "sanitization": {
            "applied": True,
            "sanitizer": SANITIZER_VERSION,
            "reason": "final_answer_locked",
            "policy_reason": policy.reason if policy else None,
            "fields": sorted(changes.fields),
            "board_item_indices": sorted(changes.board_item_indices),
            "canvas_element_ids": sorted(changes.canvas_element_ids),
            "canvas_action_ids": sorted(changes.canvas_action_ids),
            "board_action_ids": sorted(changes.board_action_ids),
            "teaching_board_element_ids": sorted(changes.teaching_board_element_ids),
            "teaching_board_action_ids": sorted(changes.teaching_board_action_ids),
        },
    }
    return validate_board_response(response.model_copy(
        update={
            "spoken_text": spoken_text,
            "display_text": display_text,
            "student_task": student_task,
            "board": board,
            "canvas": canvas,
            "canvas_actions": canvas_actions,
            "speech": speech,
            "board_actions": board_actions,
            "teaching_board": teaching_board,
            "teaching_board_history": teaching_board_history,
            "interaction": interaction,
            "next_student_action": next_student_action,
            "metadata": metadata,
        }
    ))


def _should_lock_final_answer(
    response: VisualTutorTurnResponse,
    policy: Optional[VisualTutorPolicyDecision],
) -> bool:
    if response.final_answer_locked:
        return True
    if policy is None:
        return False
    return policy.final_answer_locked and not policy.reveal_final


def _sanitize_text(text: str) -> str:
    sanitized = _ANSWER_PHRASE_RE.sub(_answer_phrase_replacement, text)
    sanitized = _COPY_ASSIGNMENT_RE.sub("Try writing the next step yourself", sanitized)
    return sanitized


def _answer_phrase_replacement(match: re.Match[str]) -> str:
    matched_text = match.group(0)
    lowered = matched_text.lower()
    if "value are" in lowered and any(
        word in lowered for word in ["we ", "you ", "trying", "need"]
    ):
        return matched_text
    return LOCKED_TEXT_REPLACEMENT


def _sanitize_board(
    board: VisualTutorBoard,
    changes: _SanitizationChanges,
) -> VisualTutorBoard:
    title = _sanitize_visible_text(board.title) if board.title else board.title
    if title != board.title:
        changes.fields.add("board")

    sanitized_items: list[VisualTutorBoardItem] = []
    for index, item in enumerate(board.items):
        sanitized_item = _sanitize_board_item(item)
        if sanitized_item != item:
            changes.fields.add("board")
            changes.board_item_indices.add(index)
        sanitized_items.append(sanitized_item)

    if sanitized_items == board.items and title == board.title:
        return board

    return board.model_copy(
        update={
            "title": title,
            "items": sanitized_items,
            "metadata": {
                **board.metadata,
                "final_answer_locked": True,
                "sanitized_by": SANITIZER_VERSION,
            },
        }
    )


def _sanitize_board_item(item: VisualTutorBoardItem) -> VisualTutorBoardItem:
    if _is_final_answer_item(item) or _looks_like_answer_assignment(item.content):
        return item.model_copy(
            update={
                "content": LOCKED_ANSWER_TEXT,
                "status": "locked",
                "metadata": {
                    **item.metadata,
                    "final_answer_locked": True,
                    "sanitized_by": SANITIZER_VERSION,
                },
            }
        )

    content = _sanitize_text(item.content)
    if content == item.content:
        return item

    return item.model_copy(
        update={
            "content": content,
            "metadata": {
                **item.metadata,
                "sanitized_by": SANITIZER_VERSION,
            },
        }
    )


def _sanitize_canvas_state(
    canvas: VisualTutorCanvasState | None,
    changes: _SanitizationChanges,
) -> VisualTutorCanvasState | None:
    if canvas is None:
        return None

    sanitized_elements: list[CanvasElement] = []
    locked_element_ids = set(canvas.locked_element_ids)
    for element in canvas.elements:
        sanitized = _sanitize_canvas_element(element)
        if sanitized != element:
            changes.fields.add("canvas")
            changes.canvas_element_ids.add(element.id)
        if sanitized.locked:
            locked_element_ids.add(sanitized.id)
        sanitized_elements.append(sanitized)

    if sanitized_elements == canvas.elements and locked_element_ids == set(
        canvas.locked_element_ids
    ):
        return canvas

    return canvas.model_copy(
        update={
            "elements": sanitized_elements,
            "locked_element_ids": sorted(locked_element_ids),
            "metadata": {
                **canvas.metadata,
                "final_answer_locked": True,
                "sanitized_by": SANITIZER_VERSION,
            },
        }
    )


def _sanitize_canvas_actions(
    actions: list[VisualTutorCanvasAction],
    changes: _SanitizationChanges,
) -> list[VisualTutorCanvasAction]:
    sanitized_actions: list[VisualTutorCanvasAction] = []
    for action in actions:
        sanitized = _sanitize_canvas_action(action)
        if sanitized != action:
            changes.fields.add("canvas_actions")
            changes.canvas_action_ids.add(action.id)
        sanitized_actions.append(sanitized)
    return sanitized_actions


def _sanitize_board_actions(
    actions: list[VisualTutorBoardAction],
    changes: _SanitizationChanges,
) -> list[VisualTutorBoardAction]:
    sanitized_actions: list[VisualTutorBoardAction] = []
    for action in actions:
        # Hard structural block: final_answer_reveal / reveal_answer actions must
        # never reach the client when the answer is locked, regardless of text
        # content. This is the primary defence; regex sanitization is secondary.
        action_type = (getattr(action, "type", None) or "").lower().strip()
        if action_type in _STRUCTURAL_ANSWER_ACTION_TYPES:
            changes.fields.add("board_actions")
            changes.board_action_ids.add(action.id)
            # Replace the reveal action with a locked placeholder action that
            # keeps the same id/position so the client can render a lock icon.
            sanitized_actions.append(action.model_copy(
                update={
                    "text": LOCKED_ANSWER_TEXT,
                    "latex": None,
                    "hidden": True,
                    "metadata": {
                        **getattr(action, "metadata", {}),
                        "final_answer_locked": True,
                        "sanitized_by": SANITIZER_VERSION,
                    },
                }
            ))
            continue
        sanitized = _sanitize_board_action(action)
        if sanitized != action:
            changes.fields.add("board_actions")
            changes.board_action_ids.add(action.id)
        sanitized_actions.append(sanitized)
    return sanitized_actions


def _sanitize_teaching_board(
    teaching_board: TeachingBoardState | None,
    changes: _SanitizationChanges,
) -> TeachingBoardState | None:
    if teaching_board is None:
        return None

    sanitized_elements: list[TeachingBoardElement] = []
    locked_ids = set(teaching_board.locked_element_ids)
    hidden_ids = set(teaching_board.hidden_element_ids)
    for element in teaching_board.elements:
        sanitized = _sanitize_teaching_board_element(element)
        if sanitized != element:
            changes.fields.add("teaching_board")
            changes.teaching_board_element_ids.add(element.id)
        if sanitized.locked:
            locked_ids.add(sanitized.id)
        if sanitized.hidden:
            hidden_ids.add(sanitized.id)
        sanitized_elements.append(sanitized)

    sanitized_actions: list[TeachingBoardAction] = []
    for action in teaching_board.actions:
        sanitized = _sanitize_teaching_board_action(action)
        if sanitized != action:
            changes.fields.add("teaching_board")
            changes.teaching_board_action_ids.add(action.id)
        sanitized_actions.append(sanitized)

    sanitized_history = _sanitize_board_history(teaching_board.history, changes)
    metadata = _sanitize_metadata(teaching_board.metadata)

    if (
        sanitized_elements == teaching_board.elements
        and sanitized_actions == teaching_board.actions
        and sanitized_history == teaching_board.history
        and locked_ids == set(teaching_board.locked_element_ids)
        and hidden_ids == set(teaching_board.hidden_element_ids)
        and metadata == teaching_board.metadata
    ):
        return teaching_board

    return teaching_board.model_copy(
        update={
            "elements": sanitized_elements,
            "actions": sanitized_actions,
            "history": sanitized_history,
            "locked_element_ids": sorted(locked_ids),
            "hidden_element_ids": sorted(hidden_ids),
            "metadata": {
                **metadata,
                "final_answer_locked": True,
                "sanitized_by": SANITIZER_VERSION,
            },
        }
    )


def _sanitize_board_history(
    history: list[BoardHistoryEntry],
    changes: _SanitizationChanges,
) -> list[BoardHistoryEntry]:
    sanitized_entries: list[BoardHistoryEntry] = []
    for entry in history:
        action = _sanitize_teaching_board_action(entry.action)
        metadata = _sanitize_metadata(entry.metadata)
        if action != entry.action or metadata != entry.metadata:
            changes.fields.add("teaching_board_history")
            changes.teaching_board_action_ids.add(entry.action.id)
            entry = entry.model_copy(
                update={
                    "action": action,
                    "metadata": {
                        **metadata,
                        "sanitized_by": SANITIZER_VERSION,
                    },
                }
            )
        sanitized_entries.append(entry)
    return sanitized_entries


def _sanitize_speech(
    speech: VisualTutorSpeech | None,
    changes: _SanitizationChanges,
) -> VisualTutorSpeech | None:
    if speech is None:
        return None
    text = _sanitize_visible_text(speech.text)
    if text == speech.text:
        return speech
    changes.fields.add("speech")
    return speech.model_copy(
        update={
            "text": text,
            "metadata": {
                **speech.metadata,
                "sanitized_by": SANITIZER_VERSION,
            },
        }
    )


def _sanitize_interaction(
    interaction: VisualTutorInteraction | None,
    changes: _SanitizationChanges,
) -> VisualTutorInteraction | None:
    if interaction is None:
        return None

    updates: dict[str, object] = {}
    prompt = _sanitize_visible_text(interaction.prompt)
    if prompt != interaction.prompt:
        updates["prompt"] = prompt
    submit_label = _sanitize_visible_text(interaction.submit_label)
    if submit_label != interaction.submit_label:
        updates["submit_label"] = submit_label

    sanitized_choices: list[VisualTutorInteractionChoice] = []
    for choice in interaction.choices:
        sanitized_choice = _sanitize_interaction_choice(choice)
        sanitized_choices.append(sanitized_choice)
    if sanitized_choices != interaction.choices:
        updates["choices"] = sanitized_choices

    if not updates:
        return interaction

    changes.fields.add("interaction")
    updates["expected_answer_locked"] = True
    updates["metadata"] = {
        **interaction.metadata,
        "sanitized_by": SANITIZER_VERSION,
    }
    return interaction.model_copy(update=updates)


def _sanitize_interaction_choice(
    choice: VisualTutorInteractionChoice,
) -> VisualTutorInteractionChoice:
    updates: dict[str, object] = {}
    label = _sanitize_visible_text(choice.label)
    if label != choice.label:
        updates["label"] = label
    value = _sanitize_visible_text(choice.value)
    if value != choice.value:
        updates["value"] = value
    if not updates:
        return choice
    updates["metadata"] = {
        **choice.metadata,
        "sanitized_by": SANITIZER_VERSION,
    }
    return choice.model_copy(update=updates)


def _sanitize_next_student_action(
    next_student_action: VisualTutorNextStudentAction | None,
    changes: _SanitizationChanges,
) -> VisualTutorNextStudentAction | None:
    if next_student_action is None:
        return None

    updates: dict[str, object] = {}
    prompt = _sanitize_visible_text(next_student_action.prompt)
    if prompt != next_student_action.prompt:
        updates["prompt"] = prompt
    submit_label = next_student_action.submit_label
    if submit_label is not None:
        sanitized_label = _sanitize_visible_text(submit_label)
        if sanitized_label != submit_label:
            updates["submit_label"] = sanitized_label

    if not updates:
        return next_student_action

    changes.fields.add("next_student_action")
    updates["expected_answer_locked"] = True
    updates["metadata"] = {
        **next_student_action.metadata,
        "sanitized_by": SANITIZER_VERSION,
    }
    return next_student_action.model_copy(update=updates)


def _sanitize_visible_text(text: str) -> str:
    if _ANSWER_PHRASE_RE.search(text):
        return LOCKED_TEXT_REPLACEMENT
    sanitized = _sanitize_text(text)
    lowered = sanitized.lower()
    if (
        "?" in sanitized
        and _ANSWER_ASSIGNMENT_RE.search(sanitized)
        and not _is_formula_like_assignment(sanitized)
        and not _assigns_only_given_values(sanitized)
    ):
        return LOCKED_TEXT_REPLACEMENT
    if _looks_like_answer_assignment(sanitized):
        return LOCKED_TEXT_REPLACEMENT
    return sanitized


def _sanitize_canvas_element(element: CanvasElement) -> CanvasElement:
    if _is_reveal_locked_canvas_payload(element) or _canvas_payload_leaks_answer(
        text=element.text,
        latex=element.latex,
    ):
        return element.model_copy(
            update={
                "text": LOCKED_ANSWER_TEXT if element.text else element.text,
                "latex": (
                    r"\text{Final answer is locked.}"
                    if element.latex
                    else element.latex
                ),
                "locked": True,
                "reveal_policy": element.reveal_policy or "final_answer_unlocked",
                "metadata": {
                    **element.metadata,
                    "hidden": True,
                    "final_answer_locked": True,
                    "sanitized_by": SANITIZER_VERSION,
                },
            }
        )

    updates: dict[str, object] = {}
    if element.text:
        sanitized_text = _sanitize_text(element.text)
        if sanitized_text != element.text:
            updates["text"] = sanitized_text
    if element.latex:
        sanitized_latex = _sanitize_text(element.latex)
        if sanitized_latex != element.latex:
            updates["latex"] = sanitized_latex
    if not updates:
        return element
    updates["metadata"] = {
        **element.metadata,
        "sanitized_by": SANITIZER_VERSION,
    }
    return element.model_copy(update=updates)


def _sanitize_teaching_board_element(
    element: TeachingBoardElement,
) -> TeachingBoardElement:
    if _is_reveal_locked_teaching_payload(element) or _teaching_payload_leaks_answer(
        text=element.text,
        latex=element.latex,
        content=element.content,
        metadata=element.metadata,
    ):
        return element.model_copy(
            update={
                "text": LOCKED_ANSWER_TEXT if element.text else element.text,
                "latex": (
                    r"\text{Final answer is locked.}"
                    if element.latex
                    else element.latex
                ),
                "content": (
                    LOCKED_ANSWER_TEXT if element.content is not None else None
                ),
                "locked": True,
                "hidden": True,
                "focus": False,
                "metadata": {
                    **_sanitize_metadata(element.metadata),
                    "hidden": True,
                    "final_answer_locked": True,
                    "sanitized_by": SANITIZER_VERSION,
                },
            }
        )

    updates: dict[str, object] = {}
    if element.text:
        sanitized_text = _sanitize_visible_text(element.text)
        if sanitized_text != element.text:
            updates["text"] = sanitized_text
    if element.latex:
        sanitized_latex = _sanitize_visible_text(element.latex)
        if sanitized_latex != element.latex:
            updates["latex"] = sanitized_latex
    if element.content is not None:
        sanitized_content = _sanitize_metadata(element.content)
        if sanitized_content != element.content:
            updates["content"] = sanitized_content
    metadata = _sanitize_metadata(element.metadata)
    if metadata != element.metadata:
        updates["metadata"] = {**metadata, "sanitized_by": SANITIZER_VERSION}
    if not updates:
        return element
    updates.setdefault(
        "metadata",
        {**element.metadata, "sanitized_by": SANITIZER_VERSION},
    )
    return element.model_copy(update=updates)


def _sanitize_canvas_action(action: VisualTutorCanvasAction) -> VisualTutorCanvasAction:
    leaks_answer = _canvas_payload_leaks_answer(
        text=action.text,
        latex=action.latex,
    )
    if _is_locked_safe_partial(action.metadata):
        leaks_answer = False
    if _is_reveal_locked_canvas_payload(action) or leaks_answer:
        return action.model_copy(
            update={
                "type": VisualTutorCanvasActionType.HIDE,
                "text": LOCKED_ANSWER_TEXT if action.text else action.text,
                "latex": (
                    r"\text{Final answer is locked.}" if action.latex else action.latex
                ),
                "locked": True,
                "reveal_policy": action.reveal_policy or "final_answer_unlocked",
                "metadata": {
                    **action.metadata,
                    "hidden": True,
                    "final_answer_locked": True,
                    "sanitized_by": SANITIZER_VERSION,
                },
            }
        )

    updates: dict[str, object] = {}
    # Deterministic solvers can explicitly mark a non-final, verified teaching
    # result (for example, a line's slope) as safe to show while the final
    # answer remains locked.  Do not let the generic answer-assignment regex
    # erase that current-step content after the leak check above accepts it.
    allow_verified_partial = _is_locked_safe_partial(action.metadata)
    if action.text and not allow_verified_partial:
        sanitized_text = _sanitize_text(action.text)
        if sanitized_text != action.text:
            updates["text"] = sanitized_text
    if action.latex and not allow_verified_partial:
        sanitized_latex = _sanitize_text(action.latex)
        if sanitized_latex != action.latex:
            updates["latex"] = sanitized_latex
    if not updates:
        return action
    updates["metadata"] = {
        **action.metadata,
        "sanitized_by": SANITIZER_VERSION,
    }
    return action.model_copy(update=updates)


def _sanitize_board_action(action: VisualTutorBoardAction) -> VisualTutorBoardAction:
    leaks_answer = _canvas_payload_leaks_answer(
        text=action.text,
        latex=action.latex,
    ) or _content_leaks_answer(getattr(action, "content", None))
    if _is_locked_safe_partial(action.metadata):
        leaks_answer = False
    if _is_reveal_locked_canvas_payload(action) or leaks_answer:
        updates = {
            "type": VisualTutorCanvasActionType.HIDE,
            "text": LOCKED_ANSWER_TEXT if action.text else action.text,
            "latex": (
                r"\text{Final answer is locked.}" if action.latex else action.latex
            ),
            "locked": True,
            "reveal_policy": action.reveal_policy or "final_answer_unlocked",
            "metadata": {
                **_sanitize_metadata(action.metadata),
                "hidden": True,
                "final_answer_locked": True,
                "sanitized_by": SANITIZER_VERSION,
            },
        }
        if getattr(action, "content", None) is not None:
            updates["content"] = LOCKED_ANSWER_TEXT
        return action.model_copy(
            update=updates,
        )

    updates: dict[str, object] = {}
    # See the equivalent canvas-action path above.  A solver-labelled partial
    # result is a legitimate current teaching step, not a final-answer leak.
    allow_verified_partial = _is_locked_safe_partial(action.metadata)
    if action.text and not allow_verified_partial:
        sanitized_text = _sanitize_text(action.text)
        if sanitized_text != action.text:
            updates["text"] = sanitized_text
    if action.latex and not allow_verified_partial:
        sanitized_latex = _sanitize_text(action.latex)
        if sanitized_latex != action.latex:
            updates["latex"] = sanitized_latex
    content = getattr(action, "content", None)
    if content is not None:
        sanitized_content = _sanitize_metadata(content)
        if sanitized_content != content:
            updates["content"] = sanitized_content
    metadata = _sanitize_metadata(action.metadata)
    if metadata != action.metadata:
        updates["metadata"] = {
            **metadata,
            "sanitized_by": SANITIZER_VERSION,
        }
    if not updates:
        return action
    updates.setdefault(
        "metadata",
        {**action.metadata, "sanitized_by": SANITIZER_VERSION},
    )
    return action.model_copy(update=updates)


def _sanitize_teaching_board_action(
    action: TeachingBoardAction,
) -> TeachingBoardAction:
    sanitized_element = (
        _sanitize_teaching_board_element(action.element)
        if action.element is not None
        else None
    )
    updates = _sanitize_metadata(action.updates)
    metadata = _sanitize_metadata(action.metadata)
    leaks = (
        _is_reveal_locked_teaching_action(action)
        or (sanitized_element is not None and sanitized_element != action.element)
        or _content_leaks_answer(updates)
        or _content_leaks_answer(metadata)
    )
    if leaks:
        metadata = {
            **metadata,
            "hidden": True,
            "final_answer_locked": True,
            "sanitized_by": SANITIZER_VERSION,
        }
        return action.model_copy(
            update={
                "type": TeachingBoardActionType.HIDE,
                "element": sanitized_element,
                "updates": updates,
                "locked": True,
                "hidden": True,
                "metadata": metadata,
            }
        )

    changes: dict[str, object] = {}
    if sanitized_element != action.element:
        changes["element"] = sanitized_element
    if updates != action.updates:
        changes["updates"] = updates
    if metadata != action.metadata:
        changes["metadata"] = {
            **metadata,
            "sanitized_by": SANITIZER_VERSION,
        }
    if not changes:
        return action
    return action.model_copy(update=changes)


def _is_reveal_locked_canvas_payload(
    payload: CanvasElement | VisualTutorCanvasAction | VisualTutorBoardAction,
) -> bool:
    metadata = payload.metadata
    reveal_policy = (payload.reveal_policy or "").lower()
    if payload.locked:
        return True
    if metadata.get("is_final_answer") is True or metadata.get("final_answer") is True:
        return True
    if metadata.get("future_step") is True:
        return True
    if str(metadata.get("solution_level", "")).lower() in {
        "full",
        "full_solution",
        "final",
    }:
        return True
    return reveal_policy in {
        "final_answer_unlocked",
        "after_final_answer_unlock",
        "after_policy_unlock",
        "full_solution_allowed",
    }


def _is_locked_safe_partial(metadata: dict) -> bool:
    return metadata.get("locked_safe_partial") is True and (
        metadata.get("is_final_answer") is not True
        and metadata.get("final_answer") is not True
    )


def _is_reveal_locked_teaching_payload(payload: TeachingBoardElement) -> bool:
    metadata = payload.metadata
    if payload.locked or payload.hidden:
        return True
    if metadata.get("is_final_answer") is True or metadata.get("final_answer") is True:
        return True
    if metadata.get("worked_example_final_answer") is True:
        return True
    if metadata.get("future_step") is True:
        return True
    if str(metadata.get("solution_level", "")).lower() in {
        "full",
        "full_solution",
        "final",
    }:
        return True
    return False


def _is_reveal_locked_teaching_action(action: TeachingBoardAction) -> bool:
    metadata = action.metadata
    if action.locked or action.hidden:
        return True
    if action.type == TeachingBoardActionType.REVEAL:
        return True
    if metadata.get("is_final_answer") is True or metadata.get("final_answer") is True:
        return True
    if metadata.get("worked_example_final_answer") is True:
        return True
    if metadata.get("future_step") is True:
        return True
    if str(metadata.get("solution_level", "")).lower() in {
        "full",
        "full_solution",
        "final",
    }:
        return True
    return False


def _canvas_payload_leaks_answer(
    *,
    text: str | None,
    latex: str | None,
) -> bool:
    return any(
        _looks_like_answer_assignment(value) or _ANSWER_PHRASE_RE.search(value)
        for value in (text or "", latex or "")
        if value
    )


def _teaching_payload_leaks_answer(
    *,
    text: str | None,
    latex: str | None,
    content: object,
    metadata: dict,
) -> bool:
    return (
        _canvas_payload_leaks_answer(text=text, latex=latex)
        or _content_leaks_answer(content)
        or _content_leaks_answer(metadata)
    )


def _content_leaks_answer(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return _looks_like_answer_assignment(value) or bool(
            _ANSWER_PHRASE_RE.search(value)
        )
    if isinstance(value, dict):
        return any(
            _metadata_key_is_answer(key) or _content_leaks_answer(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_content_leaks_answer(item) for item in value)
    return False


def _sanitize_metadata(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict = {}
        for key, item in value.items():
            if _metadata_key_allows_formula(key):
                sanitized[key] = item
            elif _metadata_key_is_answer(key):
                sanitized[key] = _locked_metadata_value(item)
            else:
                sanitized[key] = _sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    if isinstance(value, str):
        return _sanitize_visible_text(value)
    return value


def _metadata_key_is_answer(key: object) -> bool:
    lowered = str(key).lower()
    if "locked" in lowered or "lock" in lowered:
        return False
    return any(
        token in lowered
        for token in (
            "final_answer",
            "answer_key",
            "worked_example_answer",
            "solution_answer",
            "full_solution",
        )
    )


def _metadata_key_allows_formula(key: object) -> bool:
    lowered = str(key).lower()
    return any(token in lowered for token in ("formula", "formulas", "prerequisite"))


def _locked_metadata_value(value: object) -> object:
    if isinstance(value, list):
        return [LOCKED_TEXT_REPLACEMENT for _ in value]
    if isinstance(value, dict):
        return {str(key): LOCKED_TEXT_REPLACEMENT for key in value.keys()}
    return LOCKED_TEXT_REPLACEMENT


def _is_final_answer_item(item: VisualTutorBoardItem) -> bool:
    text = " ".join([item.label, item.status]).lower()
    metadata = item.metadata
    return (
        "final" in text
        or "answer" in text
        or "solution" in text
        or metadata.get("is_final_answer") is True
        or metadata.get("final_answer") is True
    )


def _looks_like_answer_assignment(text: str) -> bool:
    if "?" in text:
        return False
    lowered = text.lower()
    if "delta" in lowered or r"\delta" in lowered or "Δ" in text:
        return False
    if not _ANSWER_ASSIGNMENT_RE.search(text):
        return False

    if _is_formula_like_assignment(text):
        return False
    if _assigns_only_given_values(text):
        return False
    return True


def _normalize_number(raw: str) -> str:
    value = raw.strip().lstrip("+")
    try:
        number = float(value)
    except ValueError:
        return value.lower()
    return str(int(number)) if number.is_integer() else str(number)


def _assigns_only_given_values(text: str) -> bool:
    """True when every `var = number` in the text restates a value the
    student's own problem supplied.

    The leak rules were written for equations, where `x = 5` is the hidden
    answer. For `lim x->3 (x^2-9)/(x-3)` the tutor must say "substitute x = 3"
    to teach at all, and 3 is the approach point from the question -- the
    answer is 6. Treating that as a leak replaced every useful message with
    "Final answer is locked for now." Only values from the problem itself are
    exempt, so an equation's answer (absent from its problem text) stays
    locked, and conclusion phrasing ("so x = 3") is still caught upstream by
    _ANSWER_PHRASE_RE.
    """
    given = _GIVEN_VALUES.get()
    if not given:
        return False
    values = [_normalize_number(match) for match in _ASSIGNED_NUMBER_RE.findall(text)]
    return bool(values) and all(value in given for value in values)


def _is_formula_like_assignment(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("formula", "slope formula", "y1", "y2", "x1", "x2")
    )
