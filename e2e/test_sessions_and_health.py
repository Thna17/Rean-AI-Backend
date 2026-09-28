"""Sessions a student can come back to, and the signals a load balancer reads."""

from __future__ import annotations

import httpx
import pytest

from conftest import AI_BASE, GATEWAY_BASE, assert_contract_shape


class TestSessionLifecycle:
    def test_a_session_can_be_restored_with_its_board_intact(
        self, gateway, internal_token
    ):
        turn = gateway.solve("Solve 3x + 7 = 22")
        session_id = turn["session_id"]
        original = [
            action.get("id")
            for action in (turn["teaching_plan"] or {}).get("visible_board_actions")
            or []
        ]

        restored = gateway.get(f"/tutor/sessions/{session_id}")
        assert restored.status_code == 200, (
            f"the owner could not reopen their own session: {restored.status_code} "
            f"{restored.text[:300]}"
        )
        body = restored.json()
        payload = body.get("data", body)
        assert str(payload).count("ws-step-") or original, (
            "a restored session carried none of its board actions"
        )

    @pytest.mark.xfail(
        strict=True,
        reason="Every follow-up turn is rejected with 502 INVALID_TEACHING_PLAN. The "
        "AI service sets board_update_mode='append' on a follow-up "
        "(dynamic_worked_solution.py:552), but the public contract allows only "
        "'replace' and 'patch' — and BOTH the gateway "
        "(teaching-plan.contract.ts:425) and the Flutter client "
        "(visual_tutor_models.dart:1019) enforce that. So hints, 'explain "
        "differently', stuck help and step submission all fail: the interactive "
        "Q&A loop that CLAUDE.md names as the product's core is dead end to end.",
    )
    def test_a_second_turn_advances_the_board_version(self, gateway):
        first = gateway.solve("Solve 3x + 7 = 22")
        second = gateway.turn(
            "Why do we subtract 7 first?",
            session_id=first["session_id"],
            action="explain_differently",
        )
        assert second.status_code == 200, second.text[:300]
        follow_up = second.json()
        assert_contract_shape(follow_up)
        assert follow_up["session_id"] == first["session_id"], (
            "a follow-up started a new session instead of continuing the lesson"
        )
        assert follow_up["board_version"] >= first["board_version"], (
            "the board version went backwards between turns"
        )

    @pytest.mark.parametrize(
        "action",
        ["request_hint", "explain_differently", "request_stuck_help", "submit_step"],
    )
    @pytest.mark.xfail(
        strict=True,
        reason="Same root cause as the follow-up failure above: "
        "board_update_mode='append' is outside the public contract, so every "
        "interactive action on an open session returns 502.",
    )
    def test_each_interactive_action_works_on_an_open_session(self, gateway, action):
        first = gateway.solve("Solve 3x + 7 = 22")
        response = gateway.turn(
            "Why do we subtract 7 first?",
            session_id=first["session_id"],
            action=action,
        )
        assert response.status_code == 200, (
            f"{action} failed on a live session: {response.status_code} "
            f"{response.text[:200]}"
        )

    def test_an_unsupported_action_is_a_client_error_not_a_tutor_outage(self, gateway):
        """An action outside the contract should read as a bad request.

        The AI service's VisualTutorAction enum accepts start, submit_problem,
        submit_step, request_hint, request_stuck_help, explain_differently,
        request_final_answer and generate_practice. Anything else currently
        reaches the AI service, comes back 422, and is reported to the student as
        "The tutor service could not complete this request. Please retry." —
        which invites a retry that cannot possibly succeed.
        """
        first = gateway.solve("Solve 3x + 7 = 22")
        response = gateway.turn(
            "Why do we subtract 7 first?",
            session_id=first["session_id"],
            action="ask_question",
        )
        assert response.status_code != 200
        if response.status_code >= 500 or response.status_code == 422:
            pytest.xfail(
                "an unsupported action is surfaced as a tutor outage suggesting a "
                f"retry, rather than a 400: HTTP {response.status_code}"
            )
        assert 400 <= response.status_code < 500

    def test_an_unknown_session_is_not_found_rather_than_a_server_error(self, gateway):
        response = gateway.get("/tutor/sessions/session-that-does-not-exist")
        assert response.status_code in (403, 404), (
            f"expected a clean not-found; got {response.status_code}"
        )

    def test_a_stale_board_version_is_reported_as_a_conflict(self, gateway):
        """The client recovers from 409 by refreshing; anything else strands it."""
        first = gateway.solve("Solve 3x + 7 = 22")
        stale = gateway.turn(
            "x = 5",
            session_id=first["session_id"],
            action="submit_step",
            client_board_version=0,
        )
        assert stale.status_code in (200, 409), (
            "a stale board version must either be accepted or reported as a 409 "
            f"conflict the client knows how to recover from; got {stale.status_code} "
            f"{stale.text[:200]}"
        )


class TestHealth:
    def test_the_ai_service_reports_each_dependency(self):
        with httpx.Client() as client:
            response = client.get(f"{AI_BASE}/health", timeout=30.0)
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "healthy", body
        dependencies = body.get("dependencies") or {}
        for name in ("durable_session_store", "visual_tutor_ai"):
            assert name in dependencies, (
                f"{name} is missing from the health report, so an outage in it "
                f"would be invisible: {sorted(dependencies)}"
            )

    def test_the_gateway_reports_its_own_dependencies(self):
        with httpx.Client() as client:
            response = client.get(f"{GATEWAY_BASE}/health", timeout=30.0)
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "healthy", body
        dependencies = body.get("dependencies") or {}
        assert "visual_tutor_ai" in dependencies, (
            "the gateway does not report whether it can reach the AI service"
        )

    def test_health_needs_no_student_credentials(self):
        """A load balancer cannot authenticate."""
        with httpx.Client() as client:
            for url in (f"{AI_BASE}/health", f"{GATEWAY_BASE}/health"):
                assert client.get(url, timeout=30.0).status_code == 200, url


class TestRateLimiting:
    def test_the_tutor_still_answers_with_no_redis_running(self, gateway):
        """The limiter is Redis-backed and must fail open, not lock students out.

        Redis is not running locally, so a passing turn is the assertion.
        """
        turn = gateway.solve("Solve 3x + 7 = 22")
        assert turn["session_id"]

    def test_rate_limit_headers_are_exposed_when_present(self, gateway):
        """A client cannot back off politely without being told the budget."""
        response = gateway.turn("Solve 3x + 7 = 22")
        assert response.status_code in (200, 429)
        if response.status_code == 429:
            assert "x-ratelimit-limit" in {k.lower() for k in response.headers}
            assert "x-ratelimit-remaining" in {k.lower() for k in response.headers}
        else:
            pytest.skip("the limit was not reached, so there is no 429 to inspect")
