"""A visual tutor should draw the thing it is talking about.

Every deterministic solver emitted write_text and write_equation, and nothing
else except a table for limits. Asking the board to "sketch the graph of
y = x^2 - 4" produced ten actions of prose and algebra and no graph, because
SHOW_GRAPH only ever existed in the LLM planner path.

The client has been able to draw graphs the whole time. Its painter plots a
quadratic or a line from `function_expression`, and plots `points` for
anything else, so these builders speak exactly that grammar: lowercase, no
spaces, no `y=` prefix, and points for curves the painter cannot parse.
"""

from __future__ import annotations

import pytest

from api.services.visual_tutor.graph_actions import (
    graph_for_expression,
    graph_for_problem,
)


def _client_can_plot(expression: str) -> bool:
    """Mirrors _safePolynomialEvaluator in board_element_renderer.dart."""
    import re

    compact = expression.lower().replace(" ", "")
    if compact.startswith("y="):
        compact = compact[2:]
    quadratic = re.compile(
        r"^([+-]?(?:\d+(?:\.\d+)?)?)\*?x\^2(?:([+-]\d+(?:\.\d+)?)\*?x)?(?:([+-]\d+(?:\.\d+)?))?$"
    )
    line = re.compile(r"^([+-]?(?:\d+(?:\.\d+)?)?)\*?x(?:([+-]\d+(?:\.\d+)?))?$")
    return bool(quadratic.match(compact) or line.match(compact))


class TestExpressionGraphs:
    def test_a_quadratic_is_emitted_in_the_grammar_the_client_plots(self) -> None:
        graph = graph_for_expression("x**2 - 5*x + 6")
        assert graph is not None
        assert _client_can_plot(graph["function_expression"]), graph[
            "function_expression"
        ]

    def test_the_quadratic_roots_are_marked_on_the_curve(self) -> None:
        graph = graph_for_expression("x**2 - 5*x + 6")
        assert graph is not None
        xs = sorted(round(p["x"], 6) for p in graph["points"])
        assert xs == [2.0, 3.0]
        assert all(abs(p["y"]) < 1e-9 for p in graph["points"])

    def test_a_line_is_emitted_in_that_grammar_too(self) -> None:
        graph = graph_for_expression("2*x + 3")
        assert graph is not None
        assert _client_can_plot(graph["function_expression"])

    def test_the_window_contains_the_interesting_part_of_the_curve(self) -> None:
        # Roots at 2 and 3, vertex at x = 2.5. A window that cropped them would
        # draw a curve with nothing on it worth looking at.
        graph = graph_for_expression("x**2 - 5*x + 6")
        assert graph is not None
        assert graph["x_min"] < 2.0 and graph["x_max"] > 3.0
        assert graph["y_min"] < -0.25 < graph["y_max"]

    def test_axes_always_increase(self) -> None:
        # The contract rejects a non-increasing range, so a flat function must
        # still produce a window with height.
        graph = graph_for_expression("3")
        if graph is not None:
            assert graph["x_min"] < graph["x_max"]
            assert graph["y_min"] < graph["y_max"]

    def test_a_curve_the_client_cannot_parse_falls_back_to_points(self) -> None:
        # A cubic is beyond the painter's grammar, so sending an expression it
        # would silently drop is worse than sending samples it can draw.
        graph = graph_for_expression("x**3 - 2*x")
        assert graph is not None
        assert graph.get("function_expression") is None
        assert len(graph["points"]) >= 8

    def test_nonsense_is_refused_rather_than_guessed(self) -> None:
        assert graph_for_expression("") is None
        assert graph_for_expression("the quick brown fox") is None
        assert graph_for_expression("__import__('os')") is None

    def test_a_constant_free_of_x_is_not_worth_a_graph(self) -> None:
        assert graph_for_problem("what is 2 + 2") is None


class TestProblemGraphs:
    def test_a_quadratic_equation_in_a_sentence(self) -> None:
        graph = graph_for_problem("solve x^2 - 5x + 6 = 0")
        assert graph is not None
        assert _client_can_plot(graph["function_expression"])
        xs = sorted(round(p["x"], 6) for p in graph["points"])
        assert xs == [2.0, 3.0]

    def test_an_explicit_sketch_request(self) -> None:
        graph = graph_for_problem("sketch the graph of y = x^2 - 4")
        assert graph is not None
        assert _client_can_plot(graph["function_expression"])

    def test_a_limit_of_a_rational_function_is_drawn_as_points(self) -> None:
        # (x^2-4)/(x-2) is not a polynomial the painter parses, and it has a
        # hole at x = 2, so it is sampled instead.
        graph = graph_for_problem("lim (x^2-4)/(x-2) as x approaches 2")
        assert graph is not None
        assert len(graph["points"]) >= 8
        assert all(abs(p["y"]) < 1e6 for p in graph["points"])

    def test_a_problem_with_no_function_gets_no_graph(self) -> None:
        assert graph_for_problem("who was Isaac Newton") is None

    def test_the_payload_satisfies_both_graph_models(self) -> None:
        # Two models describe a graph and they are not the same shape: the
        # board action's spec forbids extras, has no `labels` and caps points
        # at 80, while the teaching-plan contract allows 100 and defines
        # `labels`. One payload travels through both, so it must satisfy both.
        from api.models.visual_tutor import VisualTutorGraphSpec
        from api.services.visual_tutor.teaching_plan_contract import TeachingPlanGraph

        for problem in (
            "solve x^2 - 5x + 6 = 0",
            "sketch the graph of y = x^2 - 4",
            "lim (x^2-4)/(x-2) as x approaches 2",
        ):
            graph = graph_for_problem(problem)
            assert graph is not None, problem
            TeachingPlanGraph.model_validate(graph)
            VisualTutorGraphSpec.model_validate(graph)
            assert len(graph["points"]) <= 80, "board spec caps points at 80"


@pytest.mark.parametrize(
    "expression",
    ["x**2", "-x**2 + 4", "0.5*x**2 - 2*x", "x + 1", "-3*x", "2*x - 7"],
)
def test_every_polynomial_we_claim_to_plot_is_actually_plottable(
    expression: str,
) -> None:
    graph = graph_for_expression(expression)
    assert graph is not None, expression
    assert _client_can_plot(graph["function_expression"]), graph[
        "function_expression"
    ]


class TestFocusPoint:
    """A graph has to show the part of the curve the lesson is about."""

    def test_a_limit_window_contains_the_point_being_approached(self) -> None:
        # (x^2-4)/(x-2) has its only root at x = -2, so a window built from
        # the curve alone centres there and crops out the x = 2 the student
        # asked about -- a correct graph of the wrong thing.
        without = graph_for_expression("(x^2 - 4)/(x - 2)")
        assert without is not None
        assert not (without["x_min"] <= 2.0 <= without["x_max"])

        withfocus = graph_for_expression("(x^2 - 4)/(x - 2)", focus=2.0)
        assert withfocus is not None
        assert withfocus["x_min"] < 2.0 < withfocus["x_max"]

    def test_the_focus_never_produces_a_degenerate_window(self) -> None:
        for focus in (0.0, -50.0, 50.0):
            graph = graph_for_expression("x^2 - 4", focus=focus)
            assert graph is not None, focus
            assert graph["x_min"] < graph["x_max"]
            assert graph["y_min"] < graph["y_max"]

    def test_an_unusable_focus_is_ignored_rather_than_trusted(self) -> None:
        import math

        for focus in (float("inf"), float("nan"), 1e9):
            graph = graph_for_expression("x^2 - 4", focus=focus)
            assert graph is not None, focus
            assert math.isfinite(graph["x_min"]) and math.isfinite(graph["x_max"])
            assert graph["x_min"] < graph["x_max"]
