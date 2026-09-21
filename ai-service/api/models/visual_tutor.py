from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisualTutorTeachingMode(str, Enum):
    GREETING = "greeting"
    DIAGNOSE_PROBLEM = "diagnose_problem"
    GUIDED_QUESTION = "guided_question"
    HINT = "hint"
    STEP_CHECK = "step_check"
    PARTIAL_SOLUTION = "partial_solution"
    FULL_SOLUTION = "full_solution"
    MISCONCEPTION_FIX = "misconception_fix"
    STUCK_HELP = "stuck_help"


class VisualTutorScreenState(str, Enum):
    HOME = "home"
    SPEAKING_WRITING = "speaking_writing"
    ASKING_QUESTION = "asking_question"
    GRAPH_BASED = "graph_based"
    CHECK_MY_WORK = "check_my_work"
    FINAL_VERIFIED_ANSWER = "final_verified_answer"
    UNSUPPORTED_PROBLEM = "unsupported_problem"


class VisualTutorBoardType(str, Enum):
    EQUATION = "equation"
    EQUATION_STEPS = "equation_steps"
    FORMULA_CARD = "formula_card"
    GRAPH_HINT = "graph_hint"
    TABLE = "table"
    COORDINATE_POINTS = "coordinate_points"
    WORD_PROBLEM_BREAKDOWN = "word_problem_breakdown"
    MISCONCEPTION_CARD = "misconception_card"


class VisualTutorCanvasActionType(str, Enum):
    WRITE_TEXT = "write_text"
    WRITE_EQUATION = "write_equation"
    DRAW_LINE = "draw_line"
    DRAW_RECTANGLE = "draw_rectangle"
    DRAW_ARROW = "draw_arrow"
    DRAW_POINT = "draw_point"
    DRAW_AXES = "draw_axes"
    DRAW_GRAPH_HINT = "draw_graph_hint"
    HIGHLIGHT = "highlight"
    CIRCLE = "circle"
    CROSS_OUT = "cross_out"
    SHOW_GRAPH = "show_graph"
    SHOW_TABLE = "show_table"
    CREATE_BLANK = "create_blank"
    FADE_PREVIOUS = "fade_previous"
    CLEAR_SECTION = "clear_section"
    FOCUS_ELEMENT = "focus_element"
    REVEAL_ANSWER = "reveal_answer"
    ERASE = "erase"
    FOCUS = "focus"
    REVEAL = "reveal"
    HIDE = "hide"
    SPEAK_MARKER = "speak_marker"
    PAUSE_MARKER = "pause_marker"
    TRANSFORM_EQUATION = "transform_equation"
    SHOW_NUMBER_LINE = "show_number_line"
    PLOT_FUNCTION = "plot_function"
    GRAPH_ANNOTATION = "graph_annotation"
    SHOW_HINT = "show_hint"
    SHOW_FEEDBACK = "show_feedback"
    FINAL_ANSWER_REVEAL = "final_answer_reveal"
    STUDENT_TASK = "student_task"
    DRAW_FREE_BODY_DIAGRAM = "draw_free_body_diagram"
    DRAW_MOLECULE = "draw_molecule"
    DRAW_WAVE = "draw_wave"
    DRAW_ATOM_MODEL = "draw_atom_model"
    DRAW_PARTICLE_DIAGRAM = "draw_particle_diagram"
    DRAW_CIRCUIT_DIAGRAM = "draw_circuit_diagram"
    SHOW_REACTION_LAYOUT = "show_reaction_layout"


class VisualTutorLayoutZone(str, Enum):
    PROBLEM = "problem"
    WORKING = "working"
    VISUAL = "visual"
    STUDENT_TASK = "student_task"
    REFERENCE = "reference"
    FEEDBACK = "feedback"


class VisualTutorLayoutFlow(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    OVERLAY = "overlay"
    DIAGRAM = "diagram"


class TeachingBoardElementType(str, Enum):
    TEXT = "text"
    EQUATION = "equation"
    HANDWRITING_STYLE_TEXT = "handwriting_style_text"
    POINT = "point"
    LINE = "line"
    ARROW = "arrow"
    AXES = "axes"
    GRAPH = "graph"
    TABLE = "table"
    IMAGE = "image"
    BLANK = "blank"
    HIGHLIGHT = "highlight"
    CIRCLE = "circle"
    CROSS_OUT = "cross_out"
    MISTAKE_MARKER = "mistake_marker"


class TeachingBoardActionType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    FADE = "fade"
    FOCUS = "focus"
    REVEAL = "reveal"
    HIDE = "hide"
    ERASE = "erase"
    CLEAR_SECTION = "clear_section"
    ANIMATE_PATH = "animate_path"


class VisualTutorStageState(str, Enum):
    LISTENING = "listening"
    ANALYZING = "analyzing"
    SPEAKING = "speaking"
    DRAWING = "drawing"
    WAITING_FOR_STUDENT = "waiting_for_student"
    EVALUATING = "evaluating"
    ADAPTING = "adapting"


class VisualTutorLessonState(str, Enum):
    UNDERSTAND_REQUEST = "understand_request"
    INSTANT_HELP = "instant_help"
    CHECK_STUDENT_KNOWLEDGE = "check_student_knowledge"
    TEACH = "teach"
    ASK = "ask"
    EVALUATE = "evaluate"
    RETEACH_OR_CONTINUE = "reteach_or_continue"
    VERIFY = "verify"
    COMPLETE = "complete"


class VisualTutorTtsStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    PLAYED = "played"


class VisualTutorInteractionType(str, Enum):
    TEXT_RESPONSE = "text_response"
    VOICE_RESPONSE = "voice_response"
    NUMERIC_INPUT = "numeric_input"
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    YES_NO = "yes_no"
    CONFIDENCE = "confidence"
    SELECT_BOARD_ELEMENT = "select_board_element"
    TAP_INCORRECT_STEP = "tap_incorrect_step"
    ARRANGE_STEPS = "arrange_steps"


class VisualTutorAllowedAction(str, Enum):
    SUBMIT_ANSWER = "submit_answer"
    REQUEST_HINT = "request_hint"
    EXPLAIN_DIFFERENTLY = "explain_differently"
    SHOW_VISUALLY = "show_visually"
    CHECK_WORK = "check_work"
    REQUEST_ANSWER = "request_answer"
    STUCK = "stuck"


class VisualTutorAction(str, Enum):
    START = "start"
    SUBMIT_PROBLEM = "submit_problem"
    SUBMIT_STEP = "submit_step"
    REQUEST_HINT = "request_hint"
    REQUEST_STUCK_HELP = "request_stuck_help"
    EXPLAIN_DIFFERENTLY = "explain_differently"
    REQUEST_FINAL_ANSWER = "request_final_answer"
    GENERATE_PRACTICE = "generate_practice"


class VisualTutorStudentIntent(str, Enum):
    NEW_PROBLEM = "new_problem"
    SUBMITTED_STEP = "submitted_step"
    REQUEST_HINT = "request_hint"
    REQUEST_EXPLAIN_DIFFERENTLY = "request_explain_differently"
    REQUEST_ANSWER = "request_answer"
    STUCK = "stuck"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class VisualTutorInputRelevance(str, Enum):
    RELEVANT_STEP = "relevant_step"
    POSSIBLE_FINAL_ANSWER = "possible_final_answer"
    UNRELATED = "unrelated"
    OFF_TOPIC = "off_topic"
    NEW_PROBLEM = "new_problem"
    STUCK = "stuck"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class VisualTutorInputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class VisualTutorMasterySignal(str, Enum):
    EXPLORING = "exploring"
    NEEDS_HINT = "needs_hint"
    MISCONCEPTION = "misconception"
    IMPROVING = "improving"
    READY_FOR_NEXT_STEP = "ready_for_next_step"
    MASTERED = "mastered"


class VisualTutorProblemUnderstandingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: str = Field(default="Mathematics", min_length=1)
    topic: Optional[str] = None
    message: str = Field(..., min_length=1)
    locale: Optional[str] = None
    grade_level_hint: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorProblemUnderstandingResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: str = Field(..., min_length=1)
    topic: Optional[str] = None
    problem_type: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    extracted_problem: str = Field(..., min_length=1)
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    grade_level_hint: Optional[str] = None
    known_solver_available: bool = False
    recommended_board_type: VisualTutorBoardType
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_clarification_question(
        self,
    ) -> "VisualTutorProblemUnderstandingResult":
        if self.needs_clarification and not self.clarification_question:
            raise ValueError(
                "clarification_question is required when needs_clarification is true"
            )
        return self


class VisualTutorInputUnderstandingResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    student_intent: VisualTutorStudentIntent
    input_relevance: VisualTutorInputRelevance
    confidence: float = Field(..., ge=0, le=1)
    extracted_math: Optional[str] = None
    extracted_numbers: List[str] = Field(default_factory=list)
    extracted_equations: List[str] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorStudentValidationFacts(BaseModel):
    model_config = ConfigDict(extra="allow")

    is_valid: bool = False
    is_correct: bool = False
    is_relevant: bool = False
    is_possible_final_answer: bool = False
    mistake_type: Optional[str] = None
    mistake_location: Optional[str] = None
    explanation: str = Field(default="", min_length=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorSolverFacts(BaseModel):
    model_config = ConfigDict(extra="allow")

    solver_name: str = Field(..., min_length=1)
    problem_type: str = Field(..., min_length=1)
    normalized_problem: Optional[str] = None
    variable: Optional[str] = None
    known_solution: Optional[str] = None
    current_step_index: int = Field(default=0, ge=0)
    expected_step: Optional[str] = None
    expected_operation: Optional[str] = None
    expected_equation: Optional[str] = None
    student_validation: VisualTutorStudentValidationFacts = Field(
        default_factory=VisualTutorStudentValidationFacts
    )
    verified_answer: Optional[str] = None
    sympy_verified: bool = False
    next_concept: Optional[str] = None
    safe_formulas: List[str] = Field(default_factory=list)
    board_context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorTurnState(BaseModel):
    model_config = ConfigDict(extra="allow")

    problem_instance_id: Optional[str] = None
    lesson_id: Optional[str] = None
    active_step_id: Optional[str] = None
    expected_student_action_id: Optional[str] = None
    problem_text: Optional[str] = None
    normalized_problem: Optional[str] = None
    current_step_index: int = Field(default=0, ge=0)
    hint_count: int = Field(default=0, ge=0)
    wrong_attempts: int = Field(default=0, ge=0)
    final_answer_revealed: bool = False
    student_submitted_step: bool = False


class VisualTutorBoardItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    status: str = Field(default="active", min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorBoard(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: VisualTutorBoardType
    title: Optional[str] = None
    items: List[VisualTutorBoardItem] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanvasElementStyle(BaseModel):
    model_config = ConfigDict(extra="allow")

    color: Optional[str] = None
    background_color: Optional[str] = None
    stroke_color: Optional[str] = None
    stroke_width: Optional[float] = Field(default=None, ge=0)
    font_size: Optional[float] = Field(default=None, gt=0)
    font_weight: Optional[str] = None
    opacity: Optional[float] = Field(default=None, ge=0, le=1)
    dashed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanvasViewport(BaseModel):
    model_config = ConfigDict(extra="allow")

    width: float = Field(default=1000, gt=0)
    height: float = Field(default=700, gt=0)
    x: float = 0
    y: float = 0
    scale: float = Field(default=1, gt=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanvasElement(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    text: Optional[str] = None
    latex: Optional[str] = None
    points: List[Dict[str, Any]] = Field(default_factory=list)
    target_id: Optional[str] = None
    style: CanvasElementStyle = Field(default_factory=CanvasElementStyle)
    locked: bool = False
    reveal_policy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorCanvasAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    type: VisualTutorCanvasActionType
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    text: Optional[str] = None
    latex: Optional[str] = None
    points: List[Dict[str, Any]] = Field(default_factory=list)
    target_id: Optional[str] = None
    style: CanvasElementStyle = Field(default_factory=CanvasElementStyle)
    locked: bool = False
    reveal_policy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorCanvasState(BaseModel):
    model_config = ConfigDict(extra="allow")

    viewport: CanvasViewport = Field(default_factory=CanvasViewport)
    elements: List[CanvasElement] = Field(default_factory=list)
    focus_element_id: Optional[str] = None
    locked_element_ids: List[str] = Field(default_factory=list)
    revealed_element_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingViewport(BaseModel):
    model_config = ConfigDict(extra="allow")

    width: float = Field(default=1000, gt=0)
    height: float = Field(default=700, gt=0)
    x: float = 0
    y: float = 0
    scale: float = Field(default=1, gt=0)
    min_scale: Optional[float] = Field(default=None, gt=0)
    max_scale: Optional[float] = Field(default=None, gt=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scale_bounds(self) -> "TeachingViewport":
        if (
            self.min_scale is not None
            and self.max_scale is not None
            and self.min_scale > self.max_scale
        ):
            raise ValueError("min_scale must be less than or equal to max_scale")
        return self


class TeachingBoardElement(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    type: TeachingBoardElementType
    x: float = 0
    y: float = 0
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    content: Optional[Any] = None
    text: Optional[str] = None
    latex: Optional[str] = None
    points: List[Dict[str, Any]] = Field(default_factory=list)
    style: CanvasElementStyle = Field(default_factory=CanvasElementStyle)
    opacity: float = Field(default=1, ge=0, le=1)
    group_id: Optional[str] = None
    section_id: Optional[str] = None
    z_index: int = 0
    locked: bool = False
    hidden: bool = False
    focus: bool = False
    faded: bool = False
    created_turn_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingBoardGroup(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    label: Optional[str] = None
    element_ids: List[str] = Field(default_factory=list)
    x: float = 0
    y: float = 0
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    locked: bool = False
    hidden: bool = False
    faded: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingBoardSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    label: Optional[str] = None
    x: float = 0
    y: float = 0
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    group_ids: List[str] = Field(default_factory=list)
    element_ids: List[str] = Field(default_factory=list)
    locked: bool = False
    hidden: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingBoardAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    type: TeachingBoardActionType
    element_id: Optional[str] = None
    target_id: Optional[str] = None
    section_id: Optional[str] = None
    group_id: Optional[str] = None
    element: Optional[TeachingBoardElement] = None
    updates: Dict[str, Any] = Field(default_factory=dict)
    points: List[Dict[str, Any]] = Field(default_factory=list)
    sequence_index: int = Field(default=0, ge=-1)
    duration_ms: int = Field(default=0, ge=0)
    easing: Optional[str] = None
    locked: bool = False
    hidden: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_target(self) -> "TeachingBoardAction":
        if self.type == TeachingBoardActionType.CREATE and self.element is None:
            raise ValueError("element is required for create actions")
        if self.type in {
            TeachingBoardActionType.UPDATE,
            TeachingBoardActionType.FADE,
            TeachingBoardActionType.FOCUS,
            TeachingBoardActionType.REVEAL,
            TeachingBoardActionType.HIDE,
            TeachingBoardActionType.ERASE,
            TeachingBoardActionType.ANIMATE_PATH,
        } and not (self.element_id or self.target_id):
            raise ValueError("element_id or target_id is required for this action")
        if self.type == TeachingBoardActionType.CLEAR_SECTION and not self.section_id:
            raise ValueError("section_id is required for clear_section actions")
        return self


class BoardHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    action: TeachingBoardAction
    timestamp: Optional[str] = None
    snapshot_element_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingBoardState(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default="teaching-board", min_length=1)
    viewport: TeachingViewport = Field(default_factory=TeachingViewport)
    elements: List[TeachingBoardElement] = Field(default_factory=list)
    groups: List[TeachingBoardGroup] = Field(default_factory=list)
    sections: List[TeachingBoardSection] = Field(default_factory=list)
    actions: List[TeachingBoardAction] = Field(default_factory=list)
    history: List[BoardHistoryEntry] = Field(default_factory=list)
    focus_element_id: Optional[str] = None
    active_section_id: Optional[str] = None
    locked_element_ids: List[str] = Field(default_factory=list)
    hidden_element_ids: List[str] = Field(default_factory=list)
    faded_element_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_element_state_indexes(self) -> "TeachingBoardState":
        locked_ids = set(self.locked_element_ids)
        hidden_ids = set(self.hidden_element_ids)
        faded_ids = set(self.faded_element_ids)
        for element in self.elements:
            if element.locked:
                locked_ids.add(element.id)
            if element.hidden:
                hidden_ids.add(element.id)
            if element.faded:
                faded_ids.add(element.id)
            if element.focus and not self.focus_element_id:
                self.focus_element_id = element.id
        self.locked_element_ids = sorted(locked_ids)
        self.hidden_element_ids = sorted(hidden_ids)
        self.faded_element_ids = sorted(faded_ids)
        return self


class VisualTutorSpeech(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str = Field(..., min_length=1)
    language: str = Field(default="en", min_length=1)
    voice_id: Optional[str] = None
    tts_status: VisualTutorTtsStatus = VisualTutorTtsStatus.NOT_REQUESTED
    speak_after_action_id: Optional[str] = None
    pause_after_ms: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorTeachingStage(BaseModel):
    model_config = ConfigDict(extra="allow")

    stage_state: VisualTutorStageState = VisualTutorStageState.WAITING_FOR_STUDENT
    lesson_state: VisualTutorLessonState = VisualTutorLessonState.ASK
    current_focus: Optional[str] = None
    turn_goal: Optional[str] = None
    max_actions_before_wait: int = Field(default=1, ge=1, le=12)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorGraphPoint(BaseModel):
    """A point in mathematical graph coordinates, never device pixels."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    label: Optional[str] = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_finite_coordinates(self) -> "VisualTutorGraphPoint":
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise ValueError("graph point coordinates must be finite")
        return self


class VisualTutorGraphAnnotation(BaseModel):
    """An intentional label/callout on a graph, anchored in graph coordinates."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=240)
    x: float
    y: float

    @model_validator(mode="after")
    def validate_finite_coordinates(self) -> "VisualTutorGraphAnnotation":
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise ValueError("graph annotation coordinates must be finite")
        return self


class VisualTutorGraphSpec(BaseModel):
    """Portable graph payload. Flutter receives data, never executable drawing code."""

    model_config = ConfigDict(extra="forbid")

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_label: str = Field(default="x", min_length=1, max_length=32)
    y_label: str = Field(default="y", min_length=1, max_length=32)
    function_expression: Optional[str] = Field(default=None, max_length=240)
    domain: Optional[List[float]] = None
    points: List[VisualTutorGraphPoint] = Field(default_factory=list, max_length=80)
    annotations: List[VisualTutorGraphAnnotation] = Field(
        default_factory=list, max_length=24
    )

    @model_validator(mode="after")
    def validate_graph(self) -> "VisualTutorGraphSpec":
        values = (self.x_min, self.x_max, self.y_min, self.y_max)
        if not all(math.isfinite(value) and abs(value) <= 10000 for value in values):
            raise ValueError("graph axes range is out of range")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("graph axes must have increasing ranges")
        if self.domain is not None:
            if len(self.domain) != 2 or not all(
                math.isfinite(value) for value in self.domain
            ):
                raise ValueError("graph domain must contain two finite values")
            if self.domain[0] >= self.domain[1]:
                raise ValueError("graph domain must have an increasing range")
        if not (self.function_expression or self.points):
            raise ValueError("graph requires a function_expression or points")
        return self


class VisualTutorBoardPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    label: Optional[str] = Field(default=None, max_length=120)
    open: bool = False

    @model_validator(mode="after")
    def validate_point(self) -> "VisualTutorBoardPoint":
        if not all(
            math.isfinite(value) and abs(value) <= 10000 for value in (self.x, self.y)
        ):
            raise ValueError("point coordinates are out of range")
        return self


class VisualTutorNumberLineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float = Field(ge=-10000, le=10000)
    max: float = Field(ge=-10000, le=10000)
    step: float = Field(gt=0, le=10000)
    labels: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_range(self) -> "VisualTutorNumberLineSpec":
        if (
            not math.isfinite(self.min)
            or not math.isfinite(self.max)
            or self.min >= self.max
        ):
            raise ValueError("number line range is invalid")
        if any(not label.strip() or len(label) > 120 for label in self.labels):
            raise ValueError("number line labels are invalid")
        return self


class VisualTutorTableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(min_length=1, max_length=6)
    rows: list[list[str]] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_table(self) -> "VisualTutorTableSpec":
        if any(not cell.strip() or len(cell) > 160 for cell in self.columns):
            raise ValueError("table columns are invalid")
        if any(
            len(row) != len(self.columns)
            or any(not cell.strip() or len(cell) > 160 for cell in row)
            for row in self.rows
        ):
            raise ValueError("table rows are invalid")
        return self


class VisualTutorBoardAction(BaseModel):
    # This remains a compatibility model for persisted/replay actions. It is
    # never the public renderer contract: teaching_plan_contract.py validates
    # every student-visible primitive with exact typed fields.
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    type: VisualTutorCanvasActionType
    sequence_index: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    wait_for_speech_marker: bool = False
    requires_student_response: bool = False
    group_id: Optional[str] = None
    section_id: Optional[str] = None
    layout_zone: Optional[VisualTutorLayoutZone] = None
    layout_flow: Optional[VisualTutorLayoutFlow] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    text: Optional[str] = None
    latex: Optional[str] = None
    points: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)
    graph: Optional[VisualTutorGraphSpec] = None
    label: Optional[str] = Field(default=None, max_length=120)
    number_line: Optional[VisualTutorNumberLineSpec] = None
    table: Optional[VisualTutorTableSpec] = None
    target_id: Optional[str] = None
    style: CanvasElementStyle = Field(default_factory=CanvasElementStyle)
    locked: bool = False
    reveal_policy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_renderable_action(self) -> "VisualTutorBoardAction":
        if self.type in {
            VisualTutorCanvasActionType.WRITE_TEXT,
            VisualTutorCanvasActionType.WRITE_EQUATION,
        } and not ((self.text or "").strip() or (self.latex or "").strip()):
            raise ValueError("text or latex is required for writing actions")
        if self.type in {
            VisualTutorCanvasActionType.CREATE_BLANK,
            VisualTutorCanvasActionType.SHOW_TABLE,
            VisualTutorCanvasActionType.SHOW_GRAPH,
        } and (self.width is None or self.height is None):
            raise ValueError("width and height are required for bounded board actions")
        if self.type in {
            VisualTutorCanvasActionType.DRAW_RECTANGLE,
            VisualTutorCanvasActionType.CIRCLE,
        } and (
            self.x is None
            or self.y is None
            or self.width is None
            or self.height is None
            or self.width <= 0
            or self.height <= 0
        ):
            raise ValueError("shape actions require bounded geometry")
        if (
            self.type == VisualTutorCanvasActionType.DRAW_ARROW
            and self.label is not None
        ):
            if not self.label.strip():
                raise ValueError("arrow label is invalid")
        if (
            self.type
            in {
                VisualTutorCanvasActionType.SHOW_GRAPH,
                VisualTutorCanvasActionType.PLOT_FUNCTION,
            }
            and self.graph is None
        ):
            raise ValueError("a complete graph payload is required for graph actions")
        if self.type == VisualTutorCanvasActionType.STUDENT_TASK:
            if not ((self.text or "").strip() or (self.latex or "").strip()):
                raise ValueError("student_task requires text or latex")
        if self.type == VisualTutorCanvasActionType.DRAW_FREE_BODY_DIAGRAM:
            if not isinstance(self.metadata.get("forces"), list):
                raise ValueError("forces array is required for free_body_diagram")
        if self.type == VisualTutorCanvasActionType.DRAW_MOLECULE:
            if not isinstance(self.metadata.get("atoms"), list):
                raise ValueError("atoms array is required for molecule_diagram")
        if self.type == VisualTutorCanvasActionType.DRAW_WAVE:
            if not isinstance(self.metadata.get("cycles"), (int, float)):
                raise ValueError("cycles is required for wave_diagram")
        for value in (self.x, self.y, self.width, self.height):
            if value is not None and (not math.isfinite(value) or abs(value) > 10000):
                raise ValueError("board action geometry is out of range")
        return self


class VisualTutorInteractionChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorInteraction(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: VisualTutorInteractionType
    prompt: str = Field(..., min_length=1)
    expected_answer_locked: bool = True
    validation_strategy: Optional[str] = None
    choices: List[VisualTutorInteractionChoice] = Field(default_factory=list)
    input_enabled: bool = True
    submit_label: str = Field(default="Submit", min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_choices_for_multiple_choice(self) -> "VisualTutorInteraction":
        if self.type == VisualTutorInteractionType.MULTIPLE_CHOICE and not self.choices:
            raise ValueError("choices are required for multiple_choice interaction")
        return self


class VisualTutorVisualFocus(BaseModel):
    model_config = ConfigDict(extra="allow")

    element_id: Optional[str] = None
    group_id: Optional[str] = None
    section_id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorNextStudentAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: VisualTutorInteractionType
    prompt: str = Field(..., min_length=1)
    input_enabled: bool = True
    submit_label: Optional[str] = None
    expected_answer_locked: bool = True
    validation_strategy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorBehavior(BaseModel):
    model_config = ConfigDict(extra="allow")

    should_speak: bool = True
    should_draw: bool = True
    should_ask: bool = True
    should_wait: bool = True
    should_evaluate: bool = False
    should_reteach: bool = False
    explanation_language: str = Field(default="en", min_length=1)
    tone: Optional[str] = None
    max_actions_before_wait: int = Field(default=1, ge=1, le=12)
    answer_reveal_strategy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorLanguageMode(str, Enum):
    """Student-facing explanation language; notation always stays universal."""

    KHMER = "khmer"
    ENGLISH = "english"
    BILINGUAL = "bilingual"


class VisualTutorClientTelemetryEvent(BaseModel):
    """Strictly operational client event; content and identifiers are forbidden."""
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern=r"^(action_lifecycle|latency|board_conflict|recovery)$")
    lifecycle: Optional[str] = Field(default=None, pattern=r"^(received|validated|queued|visible|rendered|skipped|off_screen)$")
    metric: Optional[str] = Field(default=None, pattern=r"^(stream_to_visible|student_to_visible)$")
    count: int = Field(default=1, ge=0, le=100)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=600000)
    outcome: Optional[str] = Field(default=None, pattern=r"^(success|failure|conflict)$")


class VisualTutorClientTelemetryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: List[VisualTutorClientTelemetryEvent] = Field(min_length=1, max_length=50)
    device_class: str = Field(pattern=r"^(mobile|tablet|desktop|landscape)$")
    viewport_bucket: str = Field(pattern=r"^(xs|sm|md|lg|xl)$")
    reduced_motion: bool


class VisualTutorTurnRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    grade: Optional[int] = None
    subject: str = Field(default="Mathematics", min_length=1)
    topic: Optional[str] = None
    message: str = Field(default="", description="Student text or transcript")
    input_type: VisualTutorInputType = VisualTutorInputType.TEXT
    locale: Optional[str] = None
    language_mode: Optional[VisualTutorLanguageMode] = None
    action: VisualTutorAction = VisualTutorAction.START
    student_intent: Optional[VisualTutorStudentIntent] = None
    current_state: VisualTutorTurnState = Field(default_factory=VisualTutorTurnState)
    hint_count: Optional[int] = Field(default=None, ge=0)
    student_submitted_step: Optional[bool] = None
    allow_final_answer: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    client_board_version: Optional[int] = None
    client_base_board_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class VisualTutorTurnResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    screen_state: VisualTutorScreenState = VisualTutorScreenState.SPEAKING_WRITING
    tutor_status: str = Field(default="Waiting", min_length=1)
    spoken_text: str = Field(..., min_length=1)
    display_text: str = Field(..., min_length=1)
    teaching_mode: VisualTutorTeachingMode
    student_intent: VisualTutorStudentIntent = VisualTutorStudentIntent.UNKNOWN
    final_answer_locked: bool
    student_task: str = Field(..., min_length=1)
    board: VisualTutorBoard
    canvas: Optional[VisualTutorCanvasState] = None
    canvas_actions: List[VisualTutorCanvasAction] = Field(default_factory=list)
    speech: Optional[VisualTutorSpeech] = None
    teaching_stage: Optional[VisualTutorTeachingStage] = None
    board_actions: List[VisualTutorBoardAction] = Field(default_factory=list)
    teaching_board: Optional[TeachingBoardState] = None
    teaching_board_history: List[BoardHistoryEntry] = Field(default_factory=list)
    interaction: Optional[VisualTutorInteraction] = None
    allowed_actions: List[VisualTutorAllowedAction] = Field(default_factory=list)
    quick_actions: List[VisualTutorAllowedAction] = Field(default_factory=list)
    visual_focus: Optional[VisualTutorVisualFocus] = None
    next_student_action: Optional[VisualTutorNextStudentAction] = None
    tutor_behavior: Optional[VisualTutorBehavior] = None
    mastery_signal: VisualTutorMasterySignal
    board_version: Optional[int] = Field(default=None)
    base_board_version: Optional[int] = Field(default=None)
    authoritative_lesson_state: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorStepTurnRequest(BaseModel):
    """Authenticated submission for one atomic expert teaching step."""

    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    subject: Literal["math", "physics", "chemistry"]
    step_id: Optional[str] = None
    message: str = Field(default="", max_length=12_000)
    action: Literal["submit", "hint", "skip"] = "submit"
    # Retained temporarily for wire compatibility, but never trusted for
    # progression. Expert rubrics must be authored in the persisted sequence.
    expected_answer: Optional[str] = Field(default=None, max_length=2_000)
    validation_strategy: Optional[str] = Field(default=None, max_length=120)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorStepTurnResponse(BaseModel):
    session_id: str
    subject: Literal["math", "physics", "chemistry"]
    current_step_index: int = Field(ge=0)
    total_steps: int = Field(ge=1)
    current_step: Dict[str, Any]
    evaluation: Optional[Dict[str, Any]] = None
    recommended_action: str
    teaching_sequence: List[Dict[str, Any]]
    expert_metadata: Dict[str, Any] = Field(default_factory=dict)
    expert_step_version: int = Field(default=0, ge=0)


class VisualTutorSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: str = Field(..., min_length=1)
    session_mode: Literal["draft", "confirmed_problem"] = "draft"
    subject: str = Field(default="Mathematics", min_length=1)
    grade_level: Optional[str] = Field(default=None, max_length=120)
    topic: Optional[str] = None
    skill_tags: List[str] = Field(default_factory=list)
    difficulty: Optional[str] = Field(default=None, max_length=80)
    problem_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_problem_for_confirmed_session(
        self,
    ) -> "VisualTutorSessionCreateRequest":
        if (
            self.session_mode == "confirmed_problem"
            and not (self.problem_text or "").strip()
        ):
            raise ValueError("A confirmed tutor session requires a problem_text")
        return self


class VisualTutorStudentModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    understanding: str = Field(default="exploring")
    recent_mistakes: List[str] = Field(default_factory=list)
    hint_level: int = Field(default=0)
    wrong_attempt_streak: int = Field(default=0)
    preferred_language: str = Field(default="en")
    preferred_explanation_level: str = Field(default="standard")
    recommended_depth: str = Field(default="standard")
    last_mastery_signal: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualTutorSession(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    session_mode: Literal["draft", "confirmed_problem"] = "draft"
    subject: str = Field(default="Mathematics", min_length=1)
    grade_level: Optional[str] = None
    topic: Optional[str] = None
    skill_tags: List[str] = Field(default_factory=list)
    difficulty: Optional[str] = None
    problem_text: Optional[str] = None
    normalized_problem: Optional[str] = None
    problem_type: Optional[str] = None
    solver_facts: Optional[Dict[str, Any]] = None
    current_step_index: int = Field(default=0, ge=0)
    expected_step: Optional[str] = None
    solved_variables: Dict[str, Any] = Field(default_factory=dict)
    validation_history: List[Dict[str, Any]] = Field(default_factory=list)
    last_verification: Optional[Dict[str, Any]] = None
    hint_count: int = Field(default=0, ge=0)
    wrong_attempts: int = Field(default=0, ge=0)
    stuck_count: int = Field(default=0, ge=0)
    attempts: int = Field(default=0, ge=0)
    final_answer_revealed: bool = False
    board_version: int = Field(default=0)
    board_schema_version: int = Field(default=1, ge=1)
    authoritative_lesson_state: Dict[str, Any] = Field(default_factory=dict)
    student_model: Optional[VisualTutorStudentModel] = Field(default=None)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    turns: List[Dict[str, Any]] = Field(default_factory=list)
    board_states: List[Dict[str, Any]] = Field(default_factory=list)
    canvas_state: Optional[Dict[str, Any]] = None
    canvas_actions: List[Dict[str, Any]] = Field(default_factory=list)
    canvas_states: List[Dict[str, Any]] = Field(default_factory=list)
    locked_canvas_element_ids: List[str] = Field(default_factory=list)
    revealed_canvas_element_ids: List[str] = Field(default_factory=list)
    current_focus_element_id: Optional[str] = None
    teaching_stage: Optional[Dict[str, Any]] = None
    stage_state: Optional[str] = None
    lesson_state: Optional[str] = None
    teaching_board_state: Optional[Dict[str, Any]] = None
    teaching_board_states: List[Dict[str, Any]] = Field(default_factory=list)
    visible_board_elements: List[Dict[str, Any]] = Field(default_factory=list)
    hidden_element_ids: List[str] = Field(default_factory=list)
    locked_element_ids: List[str] = Field(default_factory=list)
    played_action_ids: List[str] = Field(default_factory=list)
    previous_board_action_ids: List[str] = Field(default_factory=list)
    board_action_history: List[Dict[str, Any]] = Field(default_factory=list)
    replay_snapshots: List[Dict[str, Any]] = Field(default_factory=list)
    strategy_history: List[Dict[str, Any]] = Field(default_factory=list)
    pending_interaction: Optional[Dict[str, Any]] = None
    allowed_actions: List[str] = Field(default_factory=list)
    student_responses: List[Dict[str, Any]] = Field(default_factory=list)
    voice_tts_metadata: Dict[str, Any] = Field(default_factory=dict)
    curriculum_chunk_ids: List[str] = Field(default_factory=list)
    response_source_history: List[Dict[str, Any]] = Field(default_factory=list)
    mastery_signal: Optional[VisualTutorMasterySignal] = None
    status: str = Field(default="active")
    completed_at: Optional[str] = None
    targeted_practice: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    teaching_sequence: List[Dict[str, Any]] = Field(default_factory=list)
    step_evaluations: List[Dict[str, Any]] = Field(default_factory=list)
    expert_metadata: Dict[str, Any] = Field(default_factory=dict)
    expert_step_version: int = Field(default=0, ge=0)


class VisualTutorSessionSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    user_id: str
    subject: str
    grade_level: Optional[str] = None
    topic: Optional[str] = None
    skill_tags: List[str] = Field(default_factory=list)
    difficulty: Optional[str] = None
    problem_text: Optional[str] = None
    problem_type: Optional[str] = None
    current_step_index: int = 0
    expected_step: Optional[str] = None
    hint_count: int = 0
    wrong_attempts: int = 0
    stuck_count: int = 0
    attempts: int = 0
    final_answer_revealed: bool = False
    lesson_state: Optional[str] = None
    curriculum_chunk_ids: List[str] = Field(default_factory=list)
    mastery_signal: Optional[VisualTutorMasterySignal] = None
    status: str = "active"
    created_at: str
    updated_at: str


class VisualTutorSessionListResponse(BaseModel):
    sessions: List[VisualTutorSessionSummary] = Field(default_factory=list)
    total: int = 0


class PublicVisualTutorSession(BaseModel):
    """Minimal student resume DTO; persisted tutor state is server-only."""

    session_id: str
    session_mode: Literal["draft", "confirmed_problem"] = "draft"
    subject: str
    grade_level: Optional[str] = None
    topic: Optional[str] = None
    problem_text: Optional[str] = None
    current_step_index: int = 0
    hint_count: int = 0
    wrong_attempts: int = 0
    final_answer_revealed: bool = False
    board_version: int = 0
    authoritative_lesson_state: Dict[str, Any] = Field(default_factory=dict)
    curriculum_chunk_ids: List[str] = Field(default_factory=list)
    status: str = "active"
    created_at: str
    updated_at: str
