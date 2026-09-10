"""Deterministic Physics visual-plan generation for the RichMediaCanvas."""
from __future__ import annotations

import math
import re
from typing import Any

from api.models.curriculum_cambodia import RichProblem, VisualizationPlan, VisualizationStep
from api.models.teaching_step import EvaluationResult
from api.services.subject_experts._stub import StubSubjectExpert


class PhysicsExpert(StubSubjectExpert):
    """Build declarative FBD, graph, and vector plans for Phase 2 lessons."""

    subject = "physics"
    visual_type = "free_body_diagram"
    gravity_m_s2 = 9.8

    async def identify_forces(self, scenario: str) -> list[str]:
        """Identify common English and Khmer force keywords."""
        if not scenario.strip():
            raise ValueError("Scenario must not be empty")
        text = scenario.casefold()
        keywords = {
            "weight": ("weight", "gravity", "ទម្ងន់", "ទំនាញ"),
            "normal": ("normal", "surface", "incline", "ផ្ទៃ", "ទំនោរ"),
            "friction": ("friction", "rough", "កកិត"),
            "applied": ("push", "pull", "applied", "រុញ", "ទាញ"),
            "tension": ("tension", "rope", "string", "ខ្សែ"),
        }
        return [name for name, terms in keywords.items() if any(term in text for term in terms)] or ["weight", "normal"]

    async def create_free_body_diagram(self, scenario: str, forces: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Return VectorRenderer-ready FBD data; unknown forces are marked, not guessed."""
        if not scenario.strip():
            raise ValueError("Scenario must not be empty")
        mass = _number(scenario, r"(\d+(?:\.\d+)?)\s*kg")
        incline = _number(scenario, r"(?:incline|slope|ទំនោរ).*?(\d+(?:\.\d+)?)\s*(?:°|degrees?)") or 0.0
        items = list(forces or [])
        if not items:
            detected = await self.identify_forces(scenario)
            if ("weight" in detected or mass is not None) and mass is not None: items.append({"name": "Weight", "magnitude": mass * self.gravity_m_s2, "unit": "N", "direction_degrees": 270.0})
            if "normal" in detected: items.append({"name": "Normal force", "magnitude": mass * self.gravity_m_s2 * math.cos(math.radians(incline)) if mass is not None else None, "unit": "N", "direction_degrees": incline + 90, "unknown": mass is None})
            if "applied" in detected:
                magnitude = _number(scenario, r"(\d+(?:\.\d+)?)\s*N")
                items.append({"name": "Applied force", "magnitude": magnitude, "unit": "N", "direction_degrees": incline, "unknown": magnitude is None})
            if "friction" in detected: items.append({"name": "Friction", "magnitude": 0, "unit": "N", "direction_degrees": incline + 180, "unknown": True})
            if "tension" in detected: items.append({"name": "Tension", "magnitude": mass * self.gravity_m_s2 if mass is not None else None, "unit": "N", "direction_degrees": 90.0, "unknown": mass is None})
        numeric_magnitudes = [float(item["magnitude"]) for item in items if item.get("magnitude") is not None]
        scale = min(4.0, 120.0 / max(numeric_magnitudes or [1.0]))
        prepared = [{**item, "direction": f"{float(item.get('direction_degrees', 0)) % 360:g}°", "render_direction_degrees": (360 - float(item.get("direction_degrees", 0))) % 360, "visualization": {"renderer": "VectorRenderer", "pixels_per_newton": scale, "screen_y_down": True}} for item in items]
        return {"diagram_type": "free_body_diagram", "renderer": "VectorRenderer", "object": {"shape": "rectangle", "mass": mass, "unit": "kg"}, "forces": prepared, "coordinate_system": {"type": "tilted" if incline else "cartesian", "rotation_degrees": incline, "x_axis": "along incline" if incline else "horizontal", "y_axis": "normal" if incline else "vertical"}, "annotations": (["object on incline"] if incline else []) + (["force magnitude unknown"] if any(item.get("unknown") for item in items) else [])}

    async def create_motion_graphs(self, scenario: str, include_graphs: list[str] | None = None) -> list[dict[str, Any]]:
        """Create GraphRenderer specifications for constant-acceleration motion."""
        duration = _number(scenario, r"(?:in|for)\s*(\d+(?:\.\d+)?)\s*(?:s|seconds?)") or 5.0
        range_match = re.search(r"from\s*(\d+(?:\.\d+)?)\s*(?:m\s*/\s*s)?\s*to\s*(\d+(?:\.\d+)?)\s*m\s*/\s*s", scenario, flags=re.IGNORECASE)
        velocities = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*m\s*/\s*s", scenario)]
        initial, final = (float(range_match.group(1)), float(range_match.group(2))) if range_match else ((velocities[0], velocities[-1]) if velocities else (0.0, 0.0))
        acceleration = (final - initial) / duration
        sample_times = [duration * index / 10 for index in range(11)]
        specs = {"position": ("x_t", "Position vs Time", "Position (m)", [initial * time + 0.5 * acceleration * time * time for time in sample_times], "parabolic" if acceleration else "linear"), "velocity": ("v_t", "Velocity vs Time", "Velocity (m/s)", [initial + acceleration * time for time in sample_times], "linear"), "acceleration": ("a_t", "Acceleration vs Time", "Acceleration (m/s²)", [acceleration for _ in sample_times], "horizontal")}
        return [{"id": spec[0], "title": spec[1], "renderer": "GraphRenderer", "x_label": "Time (s)", "y_label": spec[2], "points": [{"x": time, "y": value} for time, value in zip(sample_times, spec[3])], "curve": spec[4], "domain": [0.0, duration]} for key in (include_graphs or ["position", "velocity", "acceleration"]) if (spec := specs.get(key))]

    async def visualize_vector_addition(self, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate a head-to-tail resultant using Cartesian components."""
        if not vectors: raise ValueError("At least one vector is required")
        prepared = []
        for vector in vectors:
            magnitude = float(vector["magnitude"]); direction = float(str(vector.get("direction", vector.get("direction_degrees", 0))).replace("°", "")); radians = math.radians(direction)
            prepared.append({**vector, "direction_degrees": direction, "x": magnitude * math.cos(radians), "y": magnitude * math.sin(radians)})
        x_total, y_total = sum(item["x"] for item in prepared), sum(item["y"] for item in prepared)
        return {"diagram_type": "vector_addition", "renderer": "VectorRenderer", "arrangement": "head_to_tail", "vectors": prepared, "resultant": {"magnitude": math.hypot(x_total, y_total), "direction_degrees": math.degrees(math.atan2(y_total, x_total)) % 360, "components": {"x": x_total, "y": y_total}}, "scale_indicator": "auto"}

    async def analyze_problem(self, problem: RichProblem) -> dict[str, Any]:
        """Extract scenario, measurable quantities, unknowns, and applicable laws."""
        analysis = await super().analyze_problem(problem)
        text = problem.problem_text
        normalized = text.casefold()
        scenario_type = _scenario_type(problem.problem_type, normalized)
        values = _given_values(text)
        analysis["scenario_type"] = scenario_type
        analysis["objects"] = [{"type": "object", "mass_kg": values.get("mass_kg")}]
        analysis["given_values"] = values
        analysis["unknowns"] = ["net_force"] if "net force" in normalized else ["acceleration"] if "acceler" in normalized else []
        analysis["applicable_laws"] = _laws_for(scenario_type)
        analysis["forces"] = await self.identify_forces(text)
        analysis["renderers"] = ["VectorRenderer", "GraphRenderer"]
        return analysis

    async def create_visualization_plan(self, problem: RichProblem, teaching_approach: str = "socratic") -> VisualizationPlan:
        """Build the six-stage physics sequence: scenario → interpretation."""
        self.validate_problem(problem, self.subject)
        fbd = await self.create_free_body_diagram(problem.problem_text)
        analysis = await self.analyze_problem(problem)
        has_motion_data = analysis["scenario_type"] == "motion" or "velocity" in problem.problem_text.casefold() or "accelerat" in problem.problem_text.casefold()
        graphs = await self.create_motion_graphs(problem.problem_text) if has_motion_data else []
        known_vectors = [{"magnitude": item["magnitude"], "direction_degrees": item["direction_degrees"]} for item in fbd["forces"] if item.get("magnitude") is not None]
        net_force = await self.visualize_vector_addition(known_vectors) if known_vectors else {"state": "await_force_magnitudes"}
        stages = [
            ("scenario", "scenario", {"renderer": "RichMediaCanvas", "scene": problem.problem_text}, "What is happening to the object?", "តើមានអ្វីកំពុងកើតឡើងចំពោះវត្ថុ?"),
            ("fbd", "free_body_diagram", fbd, "Which forces act on the object?", "តើកម្លាំងណាខ្លះមានឥទ្ធិពលលើវត្ថុ?"),
            ("net_force", "vector_analysis", {"renderer": "VectorRenderer", "forces": fbd["forces"], "resultant": net_force, "focus": "horizontal_or_motion_direction"}, "Which forces combine to give the net force?", "តើកម្លាំងណាខ្លះបូកបញ្ចូលគ្នាដើម្បីបានកម្លាំងសរុប?"),
            ("newton", "equation", {"renderer": "RichMediaCanvas", "equation": analysis["applicable_laws"][0], "given_values": analysis["given_values"]}, "Which quantity can we find using this law?", "តើបរិមាណណាដែលយើងអាចរកដោយប្រើច្បាប់នេះ?"),
            ("graphs", "motion_graphs", {"renderer": "GraphRenderer", "graphs": graphs, "state": "ready" if graphs else "await_motion_data"}, "Does the velocity-time graph agree with the acceleration?", "តើក្រាបល្បឿន-ពេលស្របនឹងសំទុះឬទេ?"),
            ("interpret", "physical_interpretation", {"renderer": "RichMediaCanvas", "summary": "Relate net force to the observed motion."}, "What does this net force mean for the object's motion?", "តើកម្លាំងសរុបនេះមានន័យដូចម្តេចចំពោះចលនារបស់វត្ថុ?"),
        ]
        steps = [VisualizationStep(step_id=f"{problem.problem_id}_{stage}", visualization_type=kind, content=content, animation_type="draw" if stage in {"fbd", "net_force"} else "fade_in", student_question=question, student_question_khmer=question_khmer, expected_response_type="text") for stage, kind, content, question, question_khmer in stages]
        return VisualizationPlan(problem_id=problem.problem_id, visualization_steps=steps, animations=[step.animation_type or "fade_in" for step in steps], student_questions=[step.student_question for step in steps], metadata={"renderer": "RichMediaCanvas", "teaching_approach": teaching_approach, "pattern": "physics_six_stage"})

    async def evaluate_student_response(self, student_answer: str, step_id: str, expected_answer: str | None = None, validation_strategy: str | None = None) -> EvaluationResult:
        """Evaluate exact answers plus common unit and conceptual equivalents."""
        if not student_answer.strip():
            raise ValueError("Student answer must not be empty")
        normalized = self.normalize_answer(student_answer)
        expected = self.normalize_answer(expected_answer) if expected_answer else None
        conceptual = {"frictionopposesmotion", "frictionopposesdirectionofmotion", "netforcecausesacceleration"}
        correct = expected is not None and (normalized == expected or normalized in conceptual)
        if validation_strategy == "numeric" and expected_answer:
            correct = _numbers_close(student_answer, expected_answer)
        return EvaluationResult(is_correct=correct, condition="correct" if correct else "incorrect", confidence=0.95 if correct else 0.8, feedback_message="Yes—your physics reasoning matches the model." if correct else "Good attempt. Check the direction, unit, and physical relationship.", should_offer_hint=not correct, hint_text=None if correct else await self.provide_hint(step_id), evaluation_time_ms=0, model_used="physics_phase_2_rules")

    async def detect_misconception(self, student_work: str, correct_answer: str, step_id: str) -> dict[str, str] | None:
        """Recognize high-impact mechanics misconceptions before generic feedback."""
        text = student_work.casefold()
        misconceptions = [
            ("heavier_falls_faster", ("heavier falls faster", "heavier object falls faster", "heavy objects fall faster"), "Without air resistance, objects have the same gravitational acceleration."),
            ("force_needed_for_motion", ("force is needed to keep moving", "moving needs force"), "A net force changes velocity; constant velocity needs zero net force."),
            ("normal_equals_weight", ("normal always equals weight",), "Normal force equals weight only in specific equilibrium situations."),
            ("acceleration_means_speeding_up", ("acceleration means speeding up",), "Acceleration is any change in velocity, including a change of direction."),
        ]
        for kind, phrases, remediation in misconceptions:
            if any(phrase in text for phrase in phrases):
                return {"misconception_type": kind, "description": "This common physics idea needs correction.", "remediation": remediation}
        return await super().detect_misconception(student_work, correct_answer, step_id)


def _number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None

def _scenario_type(problem_type: str, text: str) -> str:
    for kind, keywords in {"waves": ("wave", "frequency"), "circular_motion": ("circular", "centripetal"), "energy": ("energy", "work"), "motion": ("velocity", "accelerat", "speed"), "force": ("force", "push", "pull", "tension")}.items():
        if kind in problem_type.casefold() or any(word in text for word in keywords): return kind
    return "force"

def _given_values(text: str) -> dict[str, float]:
    patterns = {"mass_kg": r"(\d+(?:\.\d+)?)\s*kg", "force_n": r"(\d+(?:\.\d+)?)\s*N", "time_s": r"(\d+(?:\.\d+)?)\s*(?:s|seconds?)"}
    return {key: value for key, pattern in patterns.items() if (value := _number(text, pattern)) is not None}

def _laws_for(scenario_type: str) -> list[str]:
    return {"force": ["Newton's second law: F_net = ma"], "motion": ["v = u + at", "x = ut + ½at²"], "energy": ["work-energy theorem"], "waves": ["v = fλ"], "circular_motion": ["F_c = mv²/r"]}.get(scenario_type, ["Newton's laws"])

def _numbers_close(actual: str, expected: str) -> bool:
    actual_number = re.search(r"-?\d+(?:\.\d+)?", actual); expected_number = re.search(r"-?\d+(?:\.\d+)?", expected)
    return bool(actual_number and expected_number and math.isclose(float(actual_number.group()), float(expected_number.group()), rel_tol=0.03, abs_tol=0.1))
