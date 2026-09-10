"""Strict, renderer-safe teaching-plan contract for AI Visual Tutor.

The plan is intentionally data-only.  It gives the teaching orchestrator room
to select a representation and board actions without allowing generated UI or
unverified answer content to reach a client.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TEACHING_PLAN_SCHEMA_VERSION = 1
MAX_ACTIONS_PER_TURN = 24
MAX_TEXT_LENGTH = 1_000
MAX_COORDINATE = 10_000


class TeachingRepresentation(str, Enum):
    EQUATION_TRANSFORMATION = "equation_transformation"
    BALANCE_SCALE = "balance_scale"
    WORKED_EXAMPLE = "worked_example"
    NUMBER_LINE = "number_line"
    COORDINATE_GRAPH = "coordinate_graph"
    TABLE = "table"
    CONCEPTUAL_EXPLANATION = "conceptual_explanation"
    ERROR_ANALYSIS = "error_analysis"


class TeachingPlanActionType(str, Enum):
    WRITE_TEXT = "write_text"
    WRITE_EQUATION = "write_equation"
    TRANSFORM_EQUATION = "transform_equation"
    HIGHLIGHT = "highlight"
    CROSS_OUT = "cross_out"
    FADE_PREVIOUS = "fade_previous"
    SPEAK_MARKER = "speak_marker"
    PAUSE_MARKER = "pause_marker"
    DRAW_RECTANGLE = "draw_rectangle"
    CIRCLE = "circle"
    DRAW_ARROW = "draw_arrow"
    DRAW_POINT = "draw_point"
    SHOW_HINT = "show_hint"
    SHOW_FEEDBACK = "show_feedback"
    STUDENT_TASK = "student_task"
    SHOW_NUMBER_LINE = "show_number_line"
    DRAW_AXES = "draw_axes"
    SHOW_GRAPH = "show_graph"
    PLOT_FUNCTION = "plot_function"
    GRAPH_ANNOTATION = "graph_annotation"
    SHOW_TABLE = "show_table"
    DRAW_FREE_BODY_DIAGRAM = "draw_free_body_diagram"
    DRAW_MOLECULE = "draw_molecule"
    DRAW_WAVE = "draw_wave"
    DRAW_ATOM_MODEL = "draw_atom_model"
    DRAW_PARTICLE_DIAGRAM = "draw_particle_diagram"
    DRAW_CIRCUIT_DIAGRAM = "draw_circuit_diagram"
    SHOW_REACTION_LAYOUT = "show_reaction_layout"
    FINAL_ANSWER_REVEAL = "final_answer_reveal"


class TeachingPlanLayoutZone(str, Enum):
    PROBLEM = "problem"
    WORKING = "working"
    VISUAL = "visual"
    STUDENT_TASK = "student_task"
    REFERENCE = "reference"
    FEEDBACK = "feedback"


class TeachingPlanLayoutFlow(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    OVERLAY = "overlay"
    DIAGRAM = "diagram"


class HiddenAnswerMode(str, Enum):
    HIDDEN = "hidden"
    PARTIAL = "partial"
    REVEAL_ALLOWED = "reveal_allowed"


class TeachingPlanNextState(str, Enum):
    CONTINUE = "continue"
    RETEACH = "reteach"
    ASK_FOR_WORK = "ask_for_work"
    OFFER_PRACTICE = "offer_practice"
    REVEAL_PROGRESSIVELY = "reveal_progressively"
    UNSUPPORTED_RECOVERY = "unsupported_recovery"


_UNSAFE_CONTENT = re.compile(
    r"<\s*/?\s*[a-z][^>]*>|\b(?:flutter|dart|javascript|typescript|html|css|svg)\b"
    r"|\b(?:https?|javascript|data):|\b(?:widget|class|function)\s*\(",
    re.IGNORECASE,
)


def _safe_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("text must not be empty")
    if len(cleaned) > MAX_TEXT_LENGTH:
        raise ValueError("text exceeds teaching-plan limit")
    if _UNSAFE_CONTENT.search(cleaned):
        raise ValueError("generated UI code, URLs, and markup are not allowed")
    return cleaned


class TeachingPlanPoint(BaseModel):
    """A bounded data point. It is never interpreted as a rendering command."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    label: str | None = Field(default=None, max_length=120)
    open: bool = False

    @model_validator(mode="after")
    def validate_point(self) -> "TeachingPlanPoint":
        if any(abs(value) > MAX_COORDINATE for value in (self.x, self.y)):
            raise ValueError("point is outside supported board bounds")
        if self.label is not None:
            _safe_text(self.label)
        return self


class TeachingPlanAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=240)
    x: float = Field(ge=-MAX_COORDINATE, le=MAX_COORDINATE)
    y: float = Field(ge=-MAX_COORDINATE, le=MAX_COORDINATE)

    @model_validator(mode="after")
    def validate_annotation(self) -> "TeachingPlanAnnotation":
        _safe_text(self.text)
        return self


class TeachingPlanNumberLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float = Field(ge=-MAX_COORDINATE, le=MAX_COORDINATE)
    max: float = Field(ge=-MAX_COORDINATE, le=MAX_COORDINATE)
    step: float = Field(gt=0, le=MAX_COORDINATE)
    labels: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_number_line(self) -> "TeachingPlanNumberLine":
        if self.min >= self.max:
            raise ValueError("number line requires an increasing range")
        for label in self.labels:
            _safe_text(label)
            if len(label) > 120:
                raise ValueError("number line label exceeds limit")
        return self


class TeachingPlanTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(min_length=1, max_length=6)
    rows: list[list[str | int | float]] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_table(self) -> "TeachingPlanTable":
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError("table rows must match the column count")
        for cell in [*self.columns, *(item for row in self.rows for item in row)]:
            if isinstance(cell, bool):
                raise ValueError("table values must be text or finite numbers")
            if isinstance(cell, (int, float)):
                if abs(cell) > MAX_COORDINATE:
                    raise ValueError("table number exceeds limit")
            else:
                text = str(cell)
                if len(text) > 160:
                    raise ValueError("table cell exceeds limit")
                _safe_text(text)
        return self


class TeachingPlanGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    function_expression: str | None = None
    points: list[TeachingPlanPoint] = Field(default_factory=list, max_length=100)
    labels: list[str] = Field(default_factory=list, max_length=20)
    domain: list[float] | None = None
    annotations: list[TeachingPlanAnnotation] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_graph(self) -> "TeachingPlanGraph":
        values = (self.x_min, self.x_max, self.y_min, self.y_max)
        if any(abs(value) > MAX_COORDINATE for value in values):
            raise ValueError("graph axes exceed supported range")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("graph axes must have increasing ranges")
        if not self.function_expression and not self.points:
            raise ValueError("graph needs a function expression or points")
        if self.function_expression:
            _safe_text(self.function_expression)
        for label in self.labels:
            _safe_text(label)
        if self.domain is not None and len(self.domain) != 2:
            raise ValueError("graph domain must contain exactly two values")
        return self


class TeachingPlanForce(BaseModel):
    """One bounded labelled force in a free-body diagram."""

    model_config = ConfigDict(extra="forbid")

    direction: Literal["up", "down", "left", "right"]
    label: str = Field(min_length=1, max_length=80)

    @field_validator("label")
    @classmethod
    def validate_force_label(cls, value: str) -> str:
        return _safe_text(value)


class TeachingPlanAtomModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=3, pattern=r"^[A-Z][a-z]?$")
    protons: int = Field(ge=1, le=118)
    neutrons: int = Field(ge=0, le=180)
    electrons_per_shell: list[int] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def validate_atom(self) -> "TeachingPlanAtomModel":
        if any(electrons < 0 or electrons > 32 for electrons in self.electrons_per_shell):
            raise ValueError("atom shell electron count is outside supported bounds")
        if sum(self.electrons_per_shell) > 118:
            raise ValueError("atom electron count is outside supported bounds")
        return self


class TeachingPlanParticleDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["solid", "liquid", "gas"]
    particle_count: int = Field(ge=1, le=36)
    particle_label: str = Field(default="particle", min_length=1, max_length=80)

    @field_validator("particle_label")
    @classmethod
    def validate_particle_label(cls, value: str) -> str:
        return _safe_text(value)


class TeachingPlanMoleculeBond(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_index: int = Field(ge=0, le=31)
    to_index: int = Field(ge=0, le=31)
    order: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def validate_bond(self) -> "TeachingPlanMoleculeBond":
        if self.from_index == self.to_index:
            raise ValueError("molecule bond needs two distinct atoms")
        return self


class TeachingPlanCircuitComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cell", "resistor", "lamp", "switch"]
    label: str | None = Field(default=None, max_length=80)

    @field_validator("label")
    @classmethod
    def validate_component_label(cls, value: str | None) -> str | None:
        return _safe_text(value) if value is not None else None


class TeachingPlanCircuitDiagram(BaseModel):
    """A simple series circuit; Flutter chooses geometry, never the model."""

    model_config = ConfigDict(extra="forbid")

    components: list[TeachingPlanCircuitComponent] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_circuit(self) -> "TeachingPlanCircuitDiagram":
        if not any(component.kind == "cell" for component in self.components):
            raise ValueError("circuit requires one cell")
        return self


class TeachingPlanReactionLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reactants: list[str] = Field(min_length=1, max_length=4)
    products: list[str] = Field(min_length=1, max_length=4)
    coefficients: list[int] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_reaction(self) -> "TeachingPlanReactionLayout":
        for formula in [*self.reactants, *self.products]:
            if len(formula) > 80:
                raise ValueError("reaction formula exceeds limit")
            _safe_text(formula)
        if self.coefficients and len(self.coefficients) != len(self.reactants) + len(self.products):
            raise ValueError("reaction coefficients must match all formulas")
        if any(coefficient < 1 or coefficient > 99 for coefficient in self.coefficients):
            raise ValueError("reaction coefficient is outside supported bounds")
        return self


class TeachingPlanAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    type: TeachingPlanActionType
    sequence_index: int = Field(ge=0, le=MAX_ACTIONS_PER_TURN)
    duration_ms: int = Field(default=0, ge=0, le=8_000)
    wait_for_speech_marker: bool = False
    section_id: str | None = Field(
        default=None, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"
    )
    layout_zone: TeachingPlanLayoutZone | None = None
    layout_flow: TeachingPlanLayoutFlow | None = None
    x: float | None = Field(default=None, ge=-MAX_COORDINATE, le=MAX_COORDINATE)
    y: float | None = Field(default=None, ge=-MAX_COORDINATE, le=MAX_COORDINATE)
    width: float | None = Field(default=None, gt=0, le=MAX_COORDINATE)
    height: float | None = Field(default=None, gt=0, le=MAX_COORDINATE)
    text: str | None = None
    latex: str | None = None
    target_id: str | None = Field(
        default=None, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"
    )
    graph: TeachingPlanGraph | None = None
    points: list[TeachingPlanPoint] = Field(default_factory=list, max_length=100)
    label: str | None = Field(default=None, max_length=120)
    number_line: TeachingPlanNumberLine | None = None
    table: TeachingPlanTable | None = None
    forces: list[TeachingPlanForce] = Field(default_factory=list, max_length=8)
    molecule_bonds: list[TeachingPlanMoleculeBond] = Field(default_factory=list, max_length=48)
    atom_model: TeachingPlanAtomModel | None = None
    particle_diagram: TeachingPlanParticleDiagram | None = None
    circuit_diagram: TeachingPlanCircuitDiagram | None = None
    reaction_layout: TeachingPlanReactionLayout | None = None
    hidden: bool = False
    requires_student_response: bool = False
    # Only meaningful for the one active student task. This lets deterministic
    # verification use the answer form the tutor actually requested.
    task_type: Literal[
        "conceptual_operation",
        "equation_transformation",
        "numeric_value",
        "algebra_expression",
        "graph_interpretation",
    ] | None = None
    accepted_answer_forms: list[str] = Field(default_factory=list, max_length=12)
    expected_operation: str | None = Field(default=None, max_length=240)
    expected_step: str | None = Field(default=None, max_length=500)
    explanation_required: bool = False

    @field_validator("duration_ms", mode="before")
    @classmethod
    def reject_boolean_duration(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("action duration must be an integer")
        return value

    @model_validator(mode="after")
    def validate_action(self) -> "TeachingPlanAction":
        # An empty string on a field that isn't required for this action type
        # (e.g. a speak_marker/pause_marker's unused "text") is a harmless LLM
        # JSON habit, not a content violation -- only validate text that's
        # actually present. Required-but-missing text is still caught below,
        # by the text_types check, with a clearer error.
        for value in (self.text, self.latex):
            if value is not None and value.strip():
                _safe_text(value)
        text_types = {
            TeachingPlanActionType.WRITE_TEXT,
            TeachingPlanActionType.WRITE_EQUATION,
            TeachingPlanActionType.TRANSFORM_EQUATION,
            TeachingPlanActionType.SHOW_HINT,
            TeachingPlanActionType.SHOW_FEEDBACK,
            TeachingPlanActionType.STUDENT_TASK,
            TeachingPlanActionType.GRAPH_ANNOTATION,
            TeachingPlanActionType.FINAL_ANSWER_REVEAL,
        }
        if self.type in text_types and not ((self.text or "").strip() or (self.latex or "").strip()):
            raise ValueError("text action needs text or latex")
        if self.type in {TeachingPlanActionType.SHOW_GRAPH, TeachingPlanActionType.PLOT_FUNCTION} and self.graph is None:
            raise ValueError("graph action needs strict graph data")
        uses_semantic_layout = self.layout_zone is not None
        if self.type in {TeachingPlanActionType.DRAW_RECTANGLE, TeachingPlanActionType.CIRCLE}:
            if not uses_semantic_layout and None in (self.x, self.y, self.width, self.height):
                raise ValueError("shape action needs bounded geometry")
        if self.type == TeachingPlanActionType.DRAW_ARROW:
            has_box = None not in (self.x, self.y, self.width, self.height)
            if not uses_semantic_layout and not has_box and len(self.points) < 2:
                raise ValueError("arrow action needs bounded geometry or two points")
        if self.type == TeachingPlanActionType.DRAW_POINT:
            if not uses_semantic_layout and None in (self.x, self.y):
                raise ValueError("point action needs bounded coordinates")
        if self.label is not None:
            _safe_text(self.label)
        if self.type == TeachingPlanActionType.SHOW_NUMBER_LINE and self.number_line is None:
            raise ValueError("number line action needs strict number_line data")
        if self.type == TeachingPlanActionType.SHOW_TABLE and self.table is None:
            raise ValueError("table action needs strict table data")
        if self.type == TeachingPlanActionType.DRAW_FREE_BODY_DIAGRAM and not self.forces:
            raise ValueError("free body diagram needs one or more typed forces")
        if self.type == TeachingPlanActionType.DRAW_MOLECULE:
            if not self.points:
                raise ValueError("molecule diagram needs typed atom points")
            if any(bond.from_index >= len(self.points) or bond.to_index >= len(self.points) for bond in self.molecule_bonds):
                raise ValueError("molecule bond refers to an unknown atom")
        if self.type == TeachingPlanActionType.DRAW_WAVE:
            if self.width is None or self.height is None:
                raise ValueError("wave diagram needs bounded dimensions")
        if self.type == TeachingPlanActionType.DRAW_ATOM_MODEL and self.atom_model is None:
            raise ValueError("atom model needs strict atom_model data")
        if self.type == TeachingPlanActionType.DRAW_PARTICLE_DIAGRAM and self.particle_diagram is None:
            raise ValueError("particle diagram needs strict particle_diagram data")
        if self.type == TeachingPlanActionType.DRAW_CIRCUIT_DIAGRAM and self.circuit_diagram is None:
            raise ValueError("circuit diagram needs strict circuit_diagram data")
        if self.type == TeachingPlanActionType.SHOW_REACTION_LAYOUT and self.reaction_layout is None:
            raise ValueError("reaction layout needs strict reaction_layout data")
        if self.type == TeachingPlanActionType.SPEAK_MARKER and self.duration_ms != 0:
            raise ValueError("speak marker has no visual duration")
        if self.type == TeachingPlanActionType.PAUSE_MARKER and not 150 <= self.duration_ms <= 8_000:
            raise ValueError("pause marker duration must be between 150 and 8000 ms")
        if self.type == TeachingPlanActionType.STUDENT_TASK:
            if self.hidden or not self.requires_student_response:
                raise ValueError("student task must be visible and require a response")
            # Older persisted fixture plans may not have task semantics yet.
            # The active builder enriches them before they reach Flutter.
            for answer_form in self.accepted_answer_forms:
                _safe_text(answer_form)
            for value in (self.expected_operation, self.expected_step):
                if value is not None:
                    _safe_text(value)
        return self


class HiddenAnswerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: HiddenAnswerMode
    deterministic_policy_permits_final_reveal: bool = False


class TeachingPlanNextStatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct: TeachingPlanNextState
    invalid: TeachingPlanNextState
    incomplete: TeachingPlanNextState
    stuck: TeachingPlanNextState
    hint: TeachingPlanNextState
    explain_differently: TeachingPlanNextState


class VisualTutorTeachingPlan(BaseModel):
    """Data contract carried as ``metadata.teaching_plan`` until API v2."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[TEACHING_PLAN_SCHEMA_VERSION]
    representation: TeachingRepresentation
    learning_objective: str
    teaching_message: str
    board_actions: list[TeachingPlanAction] = Field(min_length=1, max_length=MAX_ACTIONS_PER_TURN)
    allowed_student_actions: list[str] = Field(min_length=1, max_length=8)
    hidden_answer_policy: HiddenAnswerPolicy
    next_state_policy: TeachingPlanNextStatePolicy

    @model_validator(mode="after")
    def validate_plan(self) -> "VisualTutorTeachingPlan":
        _safe_text(self.learning_objective)
        _safe_text(self.teaching_message)
        ids = [action.id for action in self.board_actions]
        if len(ids) != len(set(ids)):
            raise ValueError("board action IDs must be unique")
        equation_ids = {
            action.id for action in self.board_actions
            if action.type in {TeachingPlanActionType.WRITE_EQUATION, TeachingPlanActionType.TRANSFORM_EQUATION}
        }
        for action in self.board_actions:
            if action.type == TeachingPlanActionType.TRANSFORM_EQUATION and action.target_id is not None:
                if action.target_id not in equation_ids:
                    raise ValueError("equation transform target must be a board equation")
        tasks = [action for action in self.board_actions if action.type == TeachingPlanActionType.STUDENT_TASK]
        has_reveal = any(action.type == TeachingPlanActionType.FINAL_ANSWER_REVEAL for action in self.board_actions)
        if len(tasks) != (0 if has_reveal else 1):
            raise ValueError("only an authorized final-answer reveal may omit the student task")
        if has_reveal and not self.hidden_answer_policy.deterministic_policy_permits_final_reveal:
            raise ValueError("final answer reveal requires deterministic policy permission")
        if self.hidden_answer_policy.mode != HiddenAnswerMode.REVEAL_ALLOWED and has_reveal:
            raise ValueError("hidden answer policy does not permit final reveal")
        _validate_teaching_timeline(self.board_actions)
        _reject_overlapping_visual_bounds(self.board_actions)
        return self


def _reject_overlapping_visual_bounds(actions: list[TeachingPlanAction]) -> None:
    """Reject colliding explicit boxes rather than letting mobile UI overlap.

    Patch/annotation actions deliberately have no box and are excluded.  The
    renderer may lay out unpositioned actions in flow, but AI-supplied explicit
    rectangles must not cover another student-visible rectangle.
    """
    boxes: list[tuple[str, float, float, float, float]] = []
    exempt = {
        TeachingPlanActionType.HIGHLIGHT,
        TeachingPlanActionType.CROSS_OUT,
        TeachingPlanActionType.CIRCLE,
        TeachingPlanActionType.DRAW_ARROW,
        TeachingPlanActionType.DRAW_POINT,
        TeachingPlanActionType.GRAPH_ANNOTATION,
        TeachingPlanActionType.DRAW_AXES,
        TeachingPlanActionType.PLOT_FUNCTION,
        TeachingPlanActionType.FADE_PREVIOUS,
        TeachingPlanActionType.SPEAK_MARKER,
        TeachingPlanActionType.PAUSE_MARKER,
    }
    for action in actions:
        if action.type in exempt or action.layout_zone is not None or None in (action.x, action.y, action.width, action.height):
            continue
        x, y, width, height = float(action.x), float(action.y), float(action.width), float(action.height)
        for other_id, ox, oy, ow, oh in boxes:
            if x < ox + ow and x + width > ox and y < oy + oh and y + height > oy:
                raise ValueError(f"board action {action.id} overlaps {other_id}")
        boxes.append((action.id, x, y, width, height))


def _validate_teaching_timeline(actions: list[TeachingPlanAction]) -> None:
    """Keep a turn to one calm visual idea with deterministic playback markers."""
    ordered = sorted(actions, key=lambda action: (action.sequence_index, action.id))
    visual_types = {
        TeachingPlanActionType.WRITE_TEXT, TeachingPlanActionType.WRITE_EQUATION,
        TeachingPlanActionType.TRANSFORM_EQUATION, TeachingPlanActionType.DRAW_RECTANGLE,
        TeachingPlanActionType.CIRCLE, TeachingPlanActionType.DRAW_ARROW,
        TeachingPlanActionType.DRAW_POINT, TeachingPlanActionType.SHOW_NUMBER_LINE,
        TeachingPlanActionType.DRAW_AXES, TeachingPlanActionType.SHOW_GRAPH, TeachingPlanActionType.PLOT_FUNCTION,
        TeachingPlanActionType.SHOW_TABLE, TeachingPlanActionType.GRAPH_ANNOTATION,
        TeachingPlanActionType.DRAW_FREE_BODY_DIAGRAM, TeachingPlanActionType.DRAW_MOLECULE,
        TeachingPlanActionType.DRAW_WAVE, TeachingPlanActionType.DRAW_ATOM_MODEL,
        TeachingPlanActionType.DRAW_PARTICLE_DIAGRAM, TeachingPlanActionType.DRAW_CIRCUIT_DIAGRAM,
        TeachingPlanActionType.SHOW_REACTION_LAYOUT,
    }
    uses_timeline = any(
        action.type in {TeachingPlanActionType.SPEAK_MARKER, TeachingPlanActionType.PAUSE_MARKER}
        for action in ordered
    )
    # Pre-timeline sessions are persisted data, not fresh model output. Keep
    # them readable while requiring markers from every new normalized plan.
    if not uses_timeline:
        return
    visual_indexes = [index for index, action in enumerate(ordered) if action.type in visual_types]
    if len(visual_indexes) > 1:
        raise ValueError("a teaching turn may contain only one primary visual idea")
    if visual_indexes:
        visual_index = visual_indexes[0]
        if not any(action.type == TeachingPlanActionType.SPEAK_MARKER for action in ordered[:visual_index]):
            raise ValueError("a visual action needs a preceding speak marker")
        if not any(action.type == TeachingPlanActionType.PAUSE_MARKER for action in ordered[visual_index + 1:]):
            raise ValueError("a visual action needs a following pause marker")


def validate_teaching_plan(payload: Any) -> VisualTutorTeachingPlan:
    """Validate untrusted planner output immediately before it reaches a client."""
    return VisualTutorTeachingPlan.model_validate(payload)
