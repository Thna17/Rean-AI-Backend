from __future__ import annotations

import json
import math
import logging
import os
import re
import shlex
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

import httpx
from pydantic import ValidationError

from api.models.visual_tutor import (
    TeachingBoardState,
    VisualTutorAllowedAction,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorProblemUnderstandingResult,
    VisualTutorScreenState,
    VisualTutorSpeech,
    VisualTutorTeachingMode,
    VisualTutorTeachingStage,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.core.config import settings
from api.services.visual_tutor.board_contract import validate_board_response
from api.services.visual_tutor.policy import VisualTutorPolicyDecision
from api.services.visual_tutor.teaching_plan_contract import (
    TeachingPlanAction,
    TeachingPlanLayoutFlow,
    TeachingPlanLayoutZone,
    validate_teaching_plan,
)

LLM_PLANNER_VERSION = "visual_tutor_llm_teaching_planner_v1"
MAX_PLANNER_BUDGET_SECONDS = 15.0
MAX_LOCAL_CODEX_CLI_BUDGET_SECONDS = 45.0
logger = logging.getLogger(__name__)
_REQUIRED_LLM_KEYS = {
    "spoken_text",
    "display_text",
    "teaching_mode",
    "student_task",
    "board",
    "canvas_actions",
    "mastery_signal",
    "metadata",
}
_OPTIONAL_LIVE_STAGE_KEYS = {
    "screen_state",
    "tutor_status",
    "speech",
    "teaching_stage",
    "board_actions",
    "teaching_board",
    "interaction",
    "allowed_actions",
    "quick_actions",
    "teaching_plan",
}
_REQUIRED_LIVE_RESPONSE_KEYS = {
    "screen_state",
    "tutor_status",
    "speech",
    "board",
    "board_actions",
    "interaction",
    "quick_actions",
    "metadata",
}
_FINAL_ANSWER_RE = re.compile(
    r"(?i)\b(?:final\s+answer|answer|solution)\s*(?:is|:)\s*[^.\n។]+"
)
_VARIABLE_ANSWER_RE = re.compile(r"\b[a-zA-Z]\s*=\s*[-+]?\d+(?:/\d+)?(?:\.\d+)?\b")


class VisualTutorLLMClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str: ...


class OpenRouterVisualTutorLLMClient:
    def __init__(
        self,
        *,
        model: str | None = None,
        timeout: float | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.timeout = _bounded_planner_timeout(timeout)
        self.temperature = temperature

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://ai_tutor.app",
                "X-Title": "AI Tutor Visual Tutor",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]


class DeepSeekVisualTutorLLMClient:
    """DeepSeek's OpenAI-compatible JSON teaching-plan client."""

    def __init__(self, *, timeout: float | None = None, temperature: float = 0.2) -> None:
        # Keep the provider fixed server-side so a client or environment
        # typo cannot silently route student content elsewhere; the model
        # itself is still configurable since DeepSeek's own model ids move.
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
        self.timeout = _bounded_planner_timeout(timeout)
        self.temperature = temperature

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        response = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]


class GeminiVisualTutorLLMClient:
    """Production LLM client for Visual Tutor planning via Gemini API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout: float | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
        self.temperature = temperature
        from google import genai
        import google.auth
        
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            # Fall back to CLI OAuth (Application Default Credentials) via Vertex AI
            credentials, project_id = google.auth.default()
            project = os.getenv("GOOGLE_CLOUD_PROJECT", project_id) or getattr(credentials, "quota_project_id", None)
            if not project:
                raise ValueError(
                    "No GEMINI_API_KEY provided and no Google Cloud Project found in ADC. "
                    "Run `gcloud auth application-default set-quota-project YOUR_PROJECT_ID` "
                    "or set GOOGLE_CLOUD_PROJECT."
                )
            self.client = genai.Client(vertexai=True, project=project, location="us-central1")

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        from google.genai import types
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.temperature,
                response_mime_type="application/json"
            )
        )
        return response.text or ""


class OllamaVisualTutorLLMClient:
    """Local-development LLM client for Visual Tutor planning via Ollama."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
        self.timeout = _bounded_planner_timeout(
            timeout if timeout is not None else os.getenv("OLLAMA_TIMEOUT", "8")
        )
        self.temperature = temperature

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        prompt = (
            f"{system_prompt}\n\n"
            "Return only the strict JSON object for this Visual Tutor turn.\n\n"
            f"Student turn context:\n{user_prompt}"
        )
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": self.temperature,
                    "num_ctx": int(os.getenv("OLLAMA_CONTEXT_LENGTH", "4096")),
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if isinstance(message, dict) and message.get("content"):
            return str(message["content"])
        if payload.get("response"):
            return str(payload["response"])
        raise RuntimeError("Ollama planner returned no content")


class CodexCLIVisualTutorLLMClient:
    """Development-only LLM client that shells out to a signed-in Codex CLI.

    This is intended for local development on the host machine. It is not a
    production provider and should not be enabled inside Linux Docker containers,
    because the macOS Codex CLI/runtime cannot be mounted into those containers.
    """

    def __init__(
        self,
        *,
        command: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.command = command or os.getenv(
            "VISUAL_TUTOR_CODEX_CLI_COMMAND", _default_codex_cli_command()
        )
        self.timeout = _bounded_planner_timeout(
            timeout if timeout is not None else os.getenv("VISUAL_TUTOR_CODEX_CLI_TIMEOUT", "8")
        )

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        prompt = (
            f"{system_prompt}\n\n"
            "Return only the strict JSON object for this Visual Tutor turn.\n\n"
            f"Student turn context:\n{user_prompt}"
        )
        args = self._build_args(prompt)
        # `codex exec` writes progress/transcript text to stdout. Its explicit
        # last-message output is the only reliable source for the JSON plan;
        # parsing all terminal output can accidentally select JSON embedded in
        # the prompt instead of the model response.
        with tempfile.NamedTemporaryFile(prefix="visual-tutor-codex-", suffix=".json", delete=False) as handle:
            output_path = Path(handle.name)
        try:
            result = subprocess.run(
                [*args, "--output-last-message", str(output_path)],
                input=None if self._uses_prompt_arg(args) else prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise RuntimeError(
                    f"Codex CLI planner failed with exit code {result.returncode}: {stderr}"
                )
            output = output_path.read_text(encoding="utf-8").strip()
            if not output:
                raise RuntimeError("Codex CLI planner returned no output")
            return _extract_json_object(output)
        finally:
            output_path.unlink(missing_ok=True)

    def _build_args(self, prompt: str) -> list[str]:
        args = shlex.split(self.command)
        if not args:
            raise RuntimeError("VISUAL_TUTOR_CODEX_CLI_COMMAND is empty")
        return [arg.replace("{prompt}", prompt) for arg in args]

    @staticmethod
    def _uses_prompt_arg(args: list[str]) -> bool:
        return any("\n" in arg or "Student turn context:" in arg for arg in args)


def _default_codex_cli_command() -> str:
    desktop_binary = "/Applications/ChatGPT.app/Contents/Resources/codex"
    if os.path.exists(desktop_binary):
        return f"{shlex.quote(desktop_binary)} exec --ephemeral --skip-git-repo-check --ignore-rules -"
    return "codex exec --ephemeral --skip-git-repo-check --ignore-rules -"


class CodexCLIBridgeVisualTutorLLMClient:
    """Development-only client for a host-side Codex CLI bridge.

    This lets Dockerized ai-service use the user's host OAuth-backed Codex CLI
    without trying to execute a macOS binary inside a Linux container.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        timeout: float | None = None,
        token: str | None = None,
    ) -> None:
        self.url = url or os.getenv(
            "VISUAL_TUTOR_CODEX_BRIDGE_URL",
            "http://host.docker.internal:8765/complete",
        )
        self.timeout = _bounded_planner_timeout(
            timeout if timeout is not None else os.getenv("VISUAL_TUTOR_CODEX_BRIDGE_TIMEOUT", "8")
        )
        self.token = (
            token
            if token is not None
            else os.getenv("VISUAL_TUTOR_CODEX_BRIDGE_TOKEN", "")
        )

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = httpx.post(
            self.url,
            headers=headers,
            json={
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "timeout": self.timeout,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Codex CLI bridge returned no content")
        return content


class UnavailableVisualTutorLLMClient:
    """Fail-fast client used when no production LLM provider is configured."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError(self.reason)


def _default_llm_client() -> VisualTutorLLMClient:
    provider = os.getenv("VISUAL_TUTOR_LLM_PROVIDER", "auto").strip().lower()
    if provider in {"codex", "codex_cli"}:
        if _development_fallbacks_enabled():
            return CodexCLIVisualTutorLLMClient()
        return UnavailableVisualTutorLLMClient(
            "Codex CLI is development-only. Configure a hosted Visual Tutor LLM provider."
        )
    if provider in {"codex_bridge", "codex_cli_bridge", "codex_http"}:
        if _development_fallbacks_enabled():
            return CodexCLIBridgeVisualTutorLLMClient()
        return UnavailableVisualTutorLLMClient(
            "Codex CLI bridge is development-only. Configure a hosted Visual Tutor LLM provider."
        )
    if provider == "ollama":
        if _development_fallbacks_enabled():
            return OllamaVisualTutorLLMClient()
        return UnavailableVisualTutorLLMClient(
            "Ollama is development-only. Configure the hosted Visual Tutor LLM provider."
        )
    if provider == "gemini":
        return GeminiVisualTutorLLMClient()
    if provider == "openrouter":
        return OpenRouterVisualTutorLLMClient()
    if provider == "deepseek":
        return DeepSeekVisualTutorLLMClient()
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        return OpenRouterVisualTutorLLMClient()
    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        return DeepSeekVisualTutorLLMClient()
    if os.getenv("VISUAL_TUTOR_CODEX_BRIDGE_URL", "").strip() and _development_fallbacks_enabled():
        return CodexCLIBridgeVisualTutorLLMClient()
    if _development_fallbacks_enabled():
        return OllamaVisualTutorLLMClient()
    return UnavailableVisualTutorLLMClient(
        "No production Visual Tutor LLM provider configured. Set "
        "VISUAL_TUTOR_LLM_PROVIDER=deepseek with DEEPSEEK_API_KEY, openrouter with OPENROUTER_API_KEY, or "
        "VISUAL_TUTOR_LLM_PROVIDER=codex_bridge for local development."
    )


def _development_fallbacks_enabled() -> bool:
    """Development-only providers must be impossible to select in staging/prod."""
    return (
        os.getenv("ENVIRONMENT", "").strip().lower() == "development"
        and os.getenv("APP_ENV", "").strip().lower() == "development"
        and os.getenv("ALLOW_DEVELOPMENT_FALLBACKS", "false").strip().lower() == "true"
    )


def _bounded_planner_timeout(value: object | None = None) -> float:
    """Keep every provider call inside the global Visual Tutor budget."""
    raw = value
    if raw is None:
        raw = os.getenv("VISUAL_TUTOR_PLANNER_TIMEOUT_SECONDS", "8")
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        parsed = _planner_budget_cap()
    return min(_planner_budget_cap(), max(0.1, parsed))


def _planner_budget_cap() -> float:
    """Allow slower OAuth-backed Codex CLI only in explicit local dev mode."""
    provider = os.getenv("VISUAL_TUTOR_LLM_PROVIDER", "auto").strip().lower()
    if provider in {"codex", "codex_cli"} and _development_fallbacks_enabled():
        return MAX_LOCAL_CODEX_CLI_BUDGET_SECONDS
    return MAX_PLANNER_BUDGET_SECONDS


def _extract_json_object(output: str) -> str:
    cleaned = output.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Codex CLI output did not contain a JSON object")
    return cleaned[start : end + 1]


def _schema_repair_feedback(error: Exception, *, max_errors: int = 8) -> str:
    """Compact, actionable feedback for a schema-repair retry.

    A raw ValidationError dump includes the full rejected input_value per
    error, which can be huge and buries the actual problem; a repair prompt
    needs the field path and reason, not the whole payload back.
    """
    if isinstance(error, ValidationError):
        lines = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in error.errors()[:max_errors]
        ]
        return "; ".join(lines)
    return str(error)


# "More than N" -- a single stray action is normal noise; this is for a
# response where a meaningful chunk of the board didn't come through.
_BOARD_ACTION_REJECTION_RETRY_THRESHOLD = 1


def _bad_board_action_count(
    response: VisualTutorTurnResponse,
) -> tuple[int, list[str]]:
    """How many board actions the student will never see as the model
    actually authored them, and why -- used both to decide whether the
    board-action retry should fire and as the feedback text for it.

    Two distinct failure modes, both counted: _parse_board_actions() already
    silently replaces any action that fails schema validation with a generic
    "Look at the current step." placeholder (tagged
    invalid_board_action_recovered), so validate_board_response() alone
    would never see those -- by the time it runs, they already look like
    valid actions. Separately, validate_board_response() itself drops
    actions for reasons that only show up post-recovery (duplicate ids,
    more than one student task in one turn).
    """
    reasons: list[str] = []
    recovered_ids = [
        action.id
        for action in response.board_actions
        if isinstance(action.metadata, dict)
        and action.metadata.get("invalid_board_action_recovered")
    ]
    if recovered_ids:
        reasons.append(
            f"{len(recovered_ids)} action(s) failed the board-action schema "
            f"and were silently replaced with placeholder text: {recovered_ids}"
        )
    rejected_ids = validate_board_response(response).metadata.get(
        "rejected_board_action_ids"
    ) or []
    if rejected_ids:
        reasons.append(
            f"{len(rejected_ids)} action(s) were rejected outright (duplicate "
            f"id, or more than one student task in the same turn): {rejected_ids}"
        )
    return len(recovered_ids) + len(rejected_ids), reasons


def plan_visual_tutor_turn_with_llm(
    *,
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
    policy: VisualTutorPolicyDecision,
    session_id: str,
    student_model: Optional[dict] = None,
    strategy_history: Optional[list[dict[str, Any]]] = None,
    llm_client: Optional[VisualTutorLLMClient] = None,
) -> VisualTutorTurnResponse:
    client = llm_client or _default_llm_client()
    request_id = _safe_request_id(request)
    provider_name, model_name = _provider_identity(client)
    started_at = time.monotonic()
    deadline = started_at + _bounded_planner_timeout()
    schema_rejection_count = 0
    try:
        current_step_index = getattr(request.current_state, "current_step_index", None)
        system_prompt = _build_system_prompt(
            policy,
            current_step_index=current_step_index,
            problem_type=understanding.problem_type,
        )
        user_prompt = _build_user_prompt(
            request,
            understanding,
            policy,
            student_model=student_model,
            strategy_history=strategy_history,
        )
        raw_output = _complete_with_remaining_budget(
            client,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            deadline=deadline,
        )
        try:
            payload = _parse_strict_llm_json(raw_output)
            _reject_disallowed_llm_payload(payload)
        except (ValueError, ValidationError) as first_validation_error:
            schema_rejection_count = 1
            # Give a configured model one narrowly-scoped chance to repair a
            # malformed plan.  A second invalid result falls through to the
            # deterministic structured fallback below; no unsafe draft is
            # ever returned to a client.
            repaired_output = _complete_with_remaining_budget(
                client,
                system_prompt=(
                    system_prompt
                    + " Your previous output was rejected for these specific "
                    "reasons: " + _schema_repair_feedback(first_validation_error)
                    + ". Return the complete JSON again, fixing exactly these "
                    "problems. Do not add width, height, style, locked, "
                    "reveal_policy, or metadata fields to teaching_plan.board_actions "
                    "-- those belong only to the separate legacy canvas_actions list, "
                    "never to teaching_plan.board_actions. Use only the "
                    "teaching_plan.board_actions fields already described above."
                ),
                user_prompt=user_prompt,
                deadline=deadline,
            )
            try:
                payload = _parse_strict_llm_json(repaired_output)
                _reject_disallowed_llm_payload(payload)
            except (ValueError, ValidationError) as repair_error:
                schema_rejection_count = 2
                raise ValueError(
                    "LLM teaching plan remained invalid after one repair attempt: "
                    f"{repair_error}"
                ) from first_validation_error
        response = _response_from_llm_payload(
            payload=payload,
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
        )
        board_action_retry_fired = False
        board_action_rejection_count, bad_action_reasons = _bad_board_action_count(
            response
        )
        if board_action_rejection_count > _BOARD_ACTION_REJECTION_RETRY_THRESHOLD:
            board_action_retry_fired = True
            logger.warning(
                "visual_tutor board-action retry firing: %d bad action(s) (%s)",
                board_action_rejection_count,
                "; ".join(bad_action_reasons),
            )
            try:
                board_repair_output = _complete_with_remaining_budget(
                    client,
                    system_prompt=(
                        system_prompt
                        + " Your previous board_actions were rejected: "
                        + " ".join(bad_action_reasons)
                        + " Return the complete JSON again. Use only the closed set "
                        "of board-action shapes shown above, with every field they "
                        "require -- do not invent new fields or action types."
                    ),
                    user_prompt=user_prompt,
                    deadline=deadline,
                )
                board_repair_payload = _parse_strict_llm_json(board_repair_output)
                _reject_disallowed_llm_payload(board_repair_payload)
                response = _response_from_llm_payload(
                    payload=board_repair_payload,
                    request=request,
                    understanding=understanding,
                    policy=policy,
                    session_id=session_id,
                )
            except Exception as retry_error:  # noqa: BLE001
                # One retry only. If the repair attempt itself fails (bad
                # JSON, timeout, provider error), keep the original response
                # -- it already has real content, just some placeholder
                # actions -- rather than discarding it for the deterministic
                # fallback over a failed repair of a secondary problem.
                logger.warning(
                    "visual_tutor board-action retry did not produce a usable "
                    "repair, keeping the original response: %s: %s",
                    type(retry_error).__name__,
                    retry_error,
                )
        completed = response.model_copy(
            update={
                "metadata": {
                    **response.metadata,
                    **_planner_metrics(
                        request_id=request_id,
                        provider_name=provider_name,
                        model_name=model_name,
                        latency_ms=_elapsed_ms(started_at),
                        response_source="llm_planner",
                        fallback_reason=None,
                        schema_rejection_count=schema_rejection_count,
                        board_action_retry_fired=board_action_retry_fired,
                        board_action_rejection_count=board_action_rejection_count,
                    ),
                }
            }
        )
        _log_planner_metric(completed.metadata)
        return completed
    except Exception as exc:
        fallback_reason = _safe_planner_failure_reason(exc)
        response = _template_fallback_response(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            error=fallback_reason,
        )
        metrics = _planner_metrics(
            request_id=request_id,
            provider_name=provider_name,
            model_name=model_name,
            latency_ms=_elapsed_ms(started_at),
            response_source="template_fallback",
            fallback_reason=fallback_reason,
            schema_rejection_count=schema_rejection_count,
        )
        if settings.VISUAL_TUTOR_DEBUG_ERRORS:
            logger.exception(
                "visual_tutor LLM planner call failed (%s)", fallback_reason
            )
            metrics["debug_llm_error"] = _llm_debug_error_payload(exc)
        fallback = response.model_copy(
            update={"metadata": {**response.metadata, **metrics}}
        )
        _log_planner_metric(fallback.metadata)
        return fallback


def _complete_with_remaining_budget(
    client: VisualTutorLLMClient,
    *,
    system_prompt: str,
    user_prompt: str,
    deadline: float,
) -> str:
    """Do not let an output-repair attempt double the total planner budget."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Visual Tutor planner budget exhausted")
    previous_timeout = getattr(client, "timeout", None)
    if isinstance(previous_timeout, (int, float)):
        setattr(client, "timeout", min(float(previous_timeout), remaining))
    try:
        return client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    finally:
        if isinstance(previous_timeout, (int, float)):
            setattr(client, "timeout", previous_timeout)


def _safe_request_id(request: VisualTutorTurnRequest) -> str:
    candidate = str(request.metadata.get("request_id") or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{8,80}", candidate):
        return candidate
    return str(uuid.uuid4())


def _provider_identity(client: VisualTutorLLMClient) -> tuple[str, str | None]:
    if isinstance(client, OpenRouterVisualTutorLLMClient):
        return "openrouter", client.model
    if isinstance(client, DeepSeekVisualTutorLLMClient):
        return "deepseek", client.model
    if isinstance(client, OllamaVisualTutorLLMClient):
        return "ollama", client.model
    if isinstance(client, CodexCLIVisualTutorLLMClient):
        return "codex_cli", None
    if isinstance(client, CodexCLIBridgeVisualTutorLLMClient):
        return "codex_bridge", None
    if isinstance(client, UnavailableVisualTutorLLMClient):
        return "unavailable", None
    return "injected", None


def _elapsed_ms(started_at: float) -> int:
    return int((time.monotonic() - started_at) * 1000)


def _llm_debug_error_payload(exc: Exception) -> dict[str, Any]:
    """Structured detail for response.metadata['debug_llm_error'] (dev-only).

    Deliberately excludes str(exc): provider error bodies can echo back the
    student's own prompt text, and metadata must stay safe to expose. The
    full message and traceback still go to logger.exception() instead.
    """
    http_status = getattr(getattr(exc, "response", None), "status_code", None)
    payload: dict[str, Any] = {"exception_type": type(exc).__name__}
    if http_status is not None:
        payload["http_status"] = http_status
    return payload


def _safe_planner_failure_reason(error: Exception) -> str:
    if isinstance(error, (TimeoutError, subprocess.TimeoutExpired, httpx.TimeoutException)):
        return "planner_timeout"
    if isinstance(error, (ValueError, ValidationError, json.JSONDecodeError)):
        return "invalid_model_output"
    if isinstance(error, httpx.HTTPStatusError):
        return "provider_quota" if error.response.status_code == 429 else "provider_unavailable"
    return "provider_unavailable"


def _planner_metrics(
    *,
    request_id: str,
    provider_name: str,
    model_name: str | None,
    latency_ms: int,
    response_source: str,
    fallback_reason: str | None,
    schema_rejection_count: int,
    board_action_retry_fired: bool = False,
    board_action_rejection_count: int = 0,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "provider_name": provider_name,
        "model_name": model_name,
        "latency_ms": latency_ms,
        "llm_latency_ms": latency_ms,
        "response_source": response_source,
        "fallback_reason": fallback_reason,
        "schema_rejection_count": schema_rejection_count,
        "board_action_retry_fired": board_action_retry_fired,
        "board_action_rejection_count": board_action_rejection_count,
    }


def _log_planner_metric(metadata: dict[str, Any]) -> None:
    logger.info(
        "visual_tutor_planner_metric %s",
        json.dumps(
            {
                key: metadata.get(key)
                for key in (
                    "request_id", "provider_name", "model_name", "latency_ms",
                    "response_source", "fallback_reason", "schema_rejection_count",
                    "board_action_retry_fired", "board_action_rejection_count",
                )
            },
            sort_keys=True,
        ),
    )


def _parse_strict_llm_json(raw_output: str) -> Dict[str, Any]:
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("LLM planner output must be a JSON object")
    payload = _normalize_llm_payload_shape(payload)
    missing = _REQUIRED_LLM_KEYS - set(payload)
    if missing:
        raise ValueError(f"LLM planner output missing keys: {sorted(missing)}")
    allowed_keys = _REQUIRED_LLM_KEYS | _OPTIONAL_LIVE_STAGE_KEYS
    sanitized = {key: payload[key] for key in allowed_keys if key in payload}
    if "teaching_plan" in sanitized:
        # Reject the entire untrusted completion when its proposed plan is not
        # renderer-safe. The caller returns a controlled structured fallback.
        sanitized["teaching_plan"] = validate_teaching_plan(
            _drop_unknown_action_fields(sanitized["teaching_plan"])
        ).model_dump(mode="json")
    return sanitized


def _drop_unknown_action_fields(plan: Any) -> Any:
    """Strip planner drift from board actions before the contract sees them.

    The contract forbids extra keys, so one cosmetic field the model invented
    ("style", "reveal_policy", an empty "metadata") threw away an otherwise
    renderer-safe plan and dropped the student to a template fallback. This
    only ever removes data -- never invents or rewrites it -- so a plan that
    survives is exactly as trustworthy as one that needed no cleaning. The
    same allowlist approach already guards the payload's top-level keys above.
    """
    if not isinstance(plan, dict):
        return plan
    actions = plan.get("board_actions")
    if not isinstance(actions, list):
        return plan
    allowed = set(TeachingPlanAction.model_fields)
    zones = {zone.value for zone in TeachingPlanLayoutZone}
    flows = {flow.value for flow in TeachingPlanLayoutFlow}
    cleaned: list[Any] = []
    for action in actions:
        if not isinstance(action, dict):
            cleaned.append(action)
            continue
        item = {key: value for key, value in action.items() if key in allowed}
        # Both are optional with a None default, so discarding an unrecognised
        # value leaves the plan's own layout rules to decide placement rather
        # than guessing which zone the model meant.
        if item.get("layout_zone") not in zones:
            item.pop("layout_zone", None)
        if item.get("layout_flow") not in flows:
            item.pop("layout_flow", None)
        cleaned.append(item)
    return {**plan, "board_actions": cleaned}


def _reject_disallowed_llm_payload(payload: Dict[str, Any]) -> None:
    hits = _find_disallowed_llm_text(payload)
    if hits:
        raise ValueError(
            f"LLM planner output contains disallowed code/markdown: {hits[:3]}"
        )


def _find_disallowed_llm_text(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, str):
        if _looks_like_disallowed_llm_text(value):
            hits.append(path)
        return hits
    if isinstance(value, dict):
        for key, item in value.items():
            hits.extend(_find_disallowed_llm_text(item, path=f"{path}.{key}"))
        return hits
    if isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_find_disallowed_llm_text(item, path=f"{path}[{index}]"))
        return hits
    return hits


def _looks_like_disallowed_llm_text(text: str) -> bool:
    lowered = text.lower()
    return bool(
        "```" in text
        or re.search(
            r"\b(?:flutter|custompaint|buildcontext|widget\s+build|"
            r"javascript|typescript|html|svg|canvasrenderingcontext)\b",
            lowered,
        )
    )


def _normalize_llm_payload_shape(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recover useful local-model output into the strict turn schema."""
    recovered: list[str] = []
    normalized = dict(payload)

    speech = (
        normalized.get("speech") if isinstance(normalized.get("speech"), dict) else {}
    )
    interaction = (
        normalized.get("interaction")
        if isinstance(normalized.get("interaction"), dict)
        else {}
    )

    if "spoken_text" not in normalized:
        normalized["spoken_text"] = str(
            speech.get("text")
            or normalized.get("display_text")
            or "Let's inspect one useful part first."
        )
        recovered.append("spoken_text")
    if "display_text" not in normalized:
        normalized["display_text"] = str(
            normalized.get("spoken_text") or "Start with one focused step."
        )
        recovered.append("display_text")
    if "student_task" not in normalized:
        normalized["student_task"] = str(
            interaction.get("prompt") or "What should we inspect first?"
        )
        recovered.append("student_task")
    if "teaching_mode" not in normalized or not _valid_teaching_mode(
        normalized.get("teaching_mode")
    ):
        normalized["teaching_mode"] = "guided_question"
        recovered.append("teaching_mode")
    if "mastery_signal" not in normalized or not _valid_mastery_signal(
        normalized.get("mastery_signal")
    ):
        normalized["mastery_signal"] = "exploring"
        recovered.append("mastery_signal")
    if "metadata" not in normalized or not isinstance(normalized.get("metadata"), dict):
        normalized["metadata"] = {}
        recovered.append("metadata")

    if "board" not in normalized or not isinstance(normalized.get("board"), dict):
        normalized["board"] = {}
        recovered.append("board")
    else:
        board = dict(normalized["board"])
        if "type" not in board:
            board["type"] = "formula_card"
            recovered.append("board.type")
        if "title" not in board:
            board["title"] = "AI Teaching Stage"
            recovered.append("board.title")
        if "items" not in board or not isinstance(board.get("items"), list):
            content = str(
                board.get("instruction")
                or board.get("text")
                or normalized.get("display_text")
                or "Start with one focused idea."
            )
            board["items"] = [
                {
                    "label": "Focus",
                    "content": content,
                    "status": "active",
                    "metadata": {"recovered_from_llm_board": True},
                }
            ]
            recovered.append("board.items")
        if "metadata" not in board or not isinstance(board.get("metadata"), dict):
            board["metadata"] = {}
            recovered.append("board.metadata")
        normalized["board"] = board

    if "canvas_actions" not in normalized or not isinstance(
        normalized.get("canvas_actions"), list
    ):
        normalized["canvas_actions"] = []
        recovered.append("canvas_actions")

    if "board_actions" not in normalized or not isinstance(
        normalized.get("board_actions"), list
    ):
        normalized["board_actions"] = _fallback_board_actions_payload(normalized)
        recovered.append("board_actions")

    if "speech" not in normalized or not isinstance(normalized.get("speech"), dict):
        normalized["speech"] = {
            "text": normalized["spoken_text"],
            "language": "km" if _contains_khmer(normalized["spoken_text"]) else "en",
            "tts_status": "not_requested",
            "pause_after_ms": 350,
        }
        recovered.append("speech")

    if "interaction" not in normalized or not isinstance(
        normalized.get("interaction"), dict
    ):
        normalized["interaction"] = {
            "type": "text_response",
            "prompt": normalized["student_task"],
            "expected_answer_locked": True,
            "validation_strategy": "teacher_review",
            "choices": [],
            "input_enabled": True,
            "submit_label": (
                "ឆ្លើយ" if _contains_khmer(normalized["student_task"]) else "Submit"
            ),
        }
        recovered.append("interaction")

    if "allowed_actions" not in normalized or not isinstance(
        normalized.get("allowed_actions"), list
    ):
        normalized["allowed_actions"] = [
            "submit_answer",
            "request_hint",
            "explain_differently",
            "show_visually",
            "stuck",
        ]
        recovered.append("allowed_actions")
    if "quick_actions" not in normalized or not isinstance(
        normalized.get("quick_actions"), list
    ):
        normalized["quick_actions"] = list(normalized["allowed_actions"])
        recovered.append("quick_actions")
    if "screen_state" not in normalized or not _valid_screen_state(
        normalized.get("screen_state")
    ):
        normalized["screen_state"] = "speaking_writing"
        recovered.append("screen_state")
    if (
        "tutor_status" not in normalized
        or not str(normalized.get("tutor_status") or "").strip()
    ):
        normalized["tutor_status"] = (
            "Writing..." if normalized.get("board_actions") else "Waiting for you"
        )
        recovered.append("tutor_status")

    if recovered:
        metadata = normalized["metadata"]
        metadata["llm_payload_recovered_fields"] = recovered
        normalized["metadata"] = metadata
    return normalized


def _fallback_board_actions_payload(payload: Dict[str, Any]) -> list[dict[str, Any]]:
    visible_text = str(
        payload.get("display_text")
        or payload.get("student_task")
        or "Start with one useful observation."
    )
    board = payload.get("board") if isinstance(payload.get("board"), dict) else {}
    items = board.get("items") if isinstance(board.get("items"), list) else []
    if items and isinstance(items[0], dict):
        visible_text = str(items[0].get("content") or visible_text)
    return [
        {
            "id": "llm-live-speak",
            "type": "speak_marker",
            "sequence_index": 0,
            "duration_ms": 0,
            "metadata": {"source": "llm_payload_recovery"},
        },
        {
            "id": "llm-live-focus",
            "type": "write_text",
            "sequence_index": 1,
            "duration_ms": 650,
            "x": 40,
            "y": 80,
            "width": 620,
            "height": 56,
            "text": visible_text,
            "locked": False,
            "metadata": {
                "current_step": True,
                "source": "llm_payload_recovery",
                "group_id": "llm-live-focus",
            },
        },
        {
            "id": "llm-live-highlight",
            "type": "highlight",
            "sequence_index": 2,
            "duration_ms": 250,
            "target_id": "llm-live-focus",
            "metadata": {
                "reason": "current_step",
                "group_id": "llm-live-focus",
            },
        },
    ]


def _valid_teaching_mode(value: Any) -> bool:
    try:
        VisualTutorTeachingMode(value)
        return True
    except Exception:
        return False


def _valid_mastery_signal(value: Any) -> bool:
    try:
        VisualTutorMasterySignal(value)
        return True
    except Exception:
        return False


def _valid_screen_state(value: Any) -> bool:
    try:
        VisualTutorScreenState(value)
        return True
    except Exception:
        return False


def _contains_khmer(text: Any) -> bool:
    return bool(re.search(r"[\u1780-\u17ff]", str(text)))


def _response_from_llm_payload(
    *,
    payload: Dict[str, Any],
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
    policy: VisualTutorPolicyDecision,
    session_id: str,
) -> VisualTutorTurnResponse:
    try:
        board = VisualTutorBoard.model_validate(payload["board"])
    except ValidationError:
        board = _fallback_board(understanding, policy=policy)
    canvas_actions = _limit_to_one_visual_group(
        _parse_canvas_actions(payload.get("canvas_actions"))
    )
    board_actions = _limit_to_one_visual_group(
        _parse_board_actions(payload.get("board_actions"))
    )
    if not board_actions:
        board_actions = _fallback_board_actions(
            understanding,
            policy=policy,
            prompt=str(payload["student_task"]),
        )

    spoken_text = str(payload["spoken_text"])
    display_text = str(payload["display_text"])
    student_task = str(payload["student_task"])
    speech = _parse_speech(
        payload.get("speech"), fallback_text=spoken_text, policy=policy
    )
    teaching_stage = _parse_teaching_stage(payload.get("teaching_stage"))
    teaching_board = _parse_teaching_board(payload.get("teaching_board"))
    interaction = _parse_interaction(payload.get("interaction"))
    if interaction is None:
        interaction = _fallback_interaction(
            student_task,
            understanding,
            policy=policy,
            use_khmer=policy.use_khmer_explanation or understanding.language == "km",
        )
    allowed_actions = _parse_allowed_actions(payload.get("allowed_actions"))
    if not allowed_actions:
        allowed_actions = _default_allowed_actions()
    quick_actions = _parse_allowed_actions(payload.get("quick_actions"))
    if not quick_actions:
        quick_actions = allowed_actions
    screen_state = _parse_screen_state(payload.get("screen_state"))
    tutor_status = str(payload.get("tutor_status") or "Waiting for you")

    metadata = (
        payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    )
    metadata = {
        **metadata,
        "planner": LLM_PLANNER_VERSION,
        "policy": policy.metadata,
        "policy_reason": policy.reason,
        "problem_understanding": understanding.model_dump(mode="json"),
        "llm_teaching_mode": payload.get("teaching_mode"),
        "llm_mastery_signal": payload.get("mastery_signal"),
        "final_answer_locked_by_policy": policy.final_answer_locked,
        "partial_solution_allowed_by_policy": policy.partial_solution_allowed,
        "full_solution_allowed_by_policy": policy.full_solution_allowed,
        "request_student_step_by_policy": policy.request_student_step,
        "give_hint_by_policy": policy.give_hint,
        "diagnose_misconception_by_policy": policy.diagnose_misconception,
        "llm_live_stage_fields": {
            "screen_state": screen_state is not None,
            "tutor_status": bool(tutor_status),
            "speech": speech is not None,
            "teaching_stage": teaching_stage is not None,
            "board_actions": bool(board_actions),
            "teaching_board": teaching_board is not None,
            "interaction": interaction is not None,
            "allowed_actions": bool(allowed_actions),
            "quick_actions": bool(quick_actions),
        },
        "llm_required_live_fields_present": {
            key: key in payload for key in sorted(_REQUIRED_LIVE_RESPONSE_KEYS)
        },
        "screen_state": screen_state.value if screen_state else "speaking_writing",
        "tutor_status": tutor_status,
        "quick_actions": [action.value for action in quick_actions],
    }
    if isinstance(payload.get("teaching_plan"), dict):
        metadata["teaching_plan"] = payload["teaching_plan"]

    teaching_mode = (
        VisualTutorTeachingMode.GUIDED_QUESTION
        if policy.teaching_mode == VisualTutorTeachingMode.GREETING
        and policy.reason in {"new_problem_greeting", "ask_guiding_question_first"}
        else policy.teaching_mode
    )

    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=teaching_mode,
        final_answer_locked=policy.final_answer_locked,
        student_task=student_task,
        board=board,
        canvas_actions=canvas_actions,
        speech=speech,
        teaching_stage=teaching_stage,
        board_actions=board_actions,
        teaching_board=teaching_board,
        interaction=interaction,
        allowed_actions=allowed_actions,
        quick_actions=quick_actions,
        screen_state=screen_state or VisualTutorScreenState.SPEAKING_WRITING,
        tutor_status=tutor_status,
        mastery_signal=_mastery_signal(payload.get("mastery_signal")),
        metadata=metadata,
    )


def _template_fallback_response(
    *,
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
    policy: VisualTutorPolicyDecision,
    session_id: str,
    error: str,
) -> VisualTutorTurnResponse:
    use_khmer = policy.use_khmer_explanation or understanding.language == "km"
    is_stuck = policy.metadata.get("student_intent") == "stuck"
    explain_differently = policy.explain_differently or (
        policy.metadata.get("student_intent") == "request_explain_differently"
    )
    fallback_text = _subject_aware_fallback_text(
        understanding,
        use_khmer=use_khmer,
        is_stuck=is_stuck,
        explain_differently=explain_differently,
    )
    fallback_text = _solver_aware_fallback_text(
        fallback_text,
        understanding,
        policy=policy,
        use_khmer=use_khmer,
    )
    if is_stuck:
        spoken_text = fallback_text["stuck_spoken"]
        display_text = fallback_text["stuck_display"]
        student_task = fallback_text["stuck_task"]
    elif explain_differently:
        spoken_text = fallback_text["different_spoken"]
        display_text = fallback_text["different_display"]
        student_task = fallback_text["different_task"]
    else:
        spoken_text = fallback_text["default_spoken"]
        display_text = fallback_text["default_display"]
        student_task = fallback_text["default_task"]
    teaching_mode = (
        VisualTutorTeachingMode.GUIDED_QUESTION
        if policy.teaching_mode == VisualTutorTeachingMode.GREETING
        and policy.reason in {"new_problem_greeting", "ask_guiding_question_first"}
        else policy.teaching_mode
    )
    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=teaching_mode,
        final_answer_locked=policy.final_answer_locked,
        student_task=student_task,
        board=_fallback_board(understanding, policy=policy),
        canvas_actions=_fallback_canvas_actions(understanding, policy=policy),
        board_actions=_fallback_board_actions(
            understanding,
            policy=policy,
            prompt=student_task,
        ),
        interaction=_fallback_interaction(
            student_task,
            understanding,
            policy=policy,
            use_khmer=use_khmer,
        ),
        allowed_actions=_default_allowed_actions(),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={
            "planner": LLM_PLANNER_VERSION,
            "planner_fallback": True,
            "planner_error": error,
            "policy": policy.metadata,
            "policy_reason": policy.reason,
            "problem_understanding": understanding.model_dump(mode="json"),
        },
    )


def _solver_aware_fallback_text(
    fallback_text: dict[str, str],
    understanding: VisualTutorProblemUnderstandingResult,
    *,
    policy: VisualTutorPolicyDecision,
    use_khmer: bool,
) -> dict[str, str]:
    solver_facts = policy.metadata.get("solver_facts")
    if not isinstance(solver_facts, dict):
        return fallback_text
    if understanding.problem_type == "linear_equation_one_variable":
        operation = str(solver_facts.get("expected_operation") or "").strip()
        current_step_index = int(solver_facts.get("current_step_index") or 0)
        board_context = (
            solver_facts.get("board_context")
            if isinstance(solver_facts.get("board_context"), dict)
            else {}
        )
        constant = str(board_context.get("constant") or "").strip()
        coefficient = str(board_context.get("coefficient") or "").strip()
        # Once the constant has been removed, the active concept is the
        # coefficient beside the variable. Do not reuse the Step 1 constant
        # wording merely because it remains available in board_context.
        if current_step_index > 0 and coefficient:
            if use_khmer:
                return {
                    **fallback_text,
                    "default_spoken": f"ឥឡូវយើងមាន {board_context.get('first_step_equation') or ''}។ ដើម្បីទុក x ឱ្យនៅម្នាក់ឯង ចែកទាំងសងខាងដោយ {coefficient}។",
                    "default_display": f"ផ្តោតលើ {coefficient} ដែលនៅជាប់ x។ ចែកទាំងសងខាងដោយ {coefficient}។",
                    "default_task": f"តើប្រមាណវិធីណាលុប {coefficient} ដែលនៅជាប់ x?",
                    "stuck_spoken": f"មិនអីទេ។ យើងត្រូវលុប {coefficient} ដែលនៅជាប់ x ប៉ុណ្ណោះ។",
                    "stuck_display": f"គន្លឹះ៖ ចែកទាំងសងខាងដោយ {coefficient}។",
                    "stuck_task": f"តើអ្វីលុប {coefficient} ដែលនៅជាប់ x?",
                    "different_spoken": "គិតដូចតុល្យភាព៖ ធ្វើដូចគ្នាលើទាំងសងខាង។",
                    "different_display": f"វិធីផ្សេង៖ ចែកទាំងសងខាងដោយ {coefficient} ដើម្បីទុក x ឱ្យនៅម្នាក់ឯង។",
                    "different_task": f"តើត្រូវចែកទាំងសងខាងដោយប៉ុន្មាន?",
                }
            return {
                **fallback_text,
                "default_spoken": f"We now have {board_context.get('first_step_equation') or 'the simplified equation'}. To leave x alone, divide both sides by {coefficient}.",
                "default_display": f"Focus on the {coefficient} beside x. Divide both sides by {coefficient}.",
                "default_task": f"What operation cancels the {coefficient} beside x?",
                "stuck_spoken": f"That is okay. We only need to cancel the {coefficient} beside x.",
                "stuck_display": f"Hint: divide both sides by {coefficient}.",
                "stuck_task": f"What cancels the {coefficient} beside x?",
                "different_spoken": "Think of the equation like a balance scale: do the same move to both sides.",
                "different_display": f"Different view: divide both sides by {coefficient} so x is alone.",
                "different_task": "What should we divide both sides by?",
            }
        if operation:
            if use_khmer:
                return {
                    **fallback_text,
                    "default_spoken": f"មើលចំនួនថេរ {constant or ''} សិន។ តើធ្វើអ្វីដើម្បីលុបវា?",
                    "default_display": f"ផ្តោតលើចំនួនថេរ {constant or ''}។ ប្រើប្រមាណវិធីផ្ទុយ។",
                    "default_task": f"តើប្រមាណវិធីណាដំបូង? {operation} ឬអ្វីផ្សេង?",
                    "stuck_spoken": f"មិនអីទេ។ យើងផ្តោតតែចំនួនថេរ {constant or ''} មួយសិន។",
                    "stuck_display": f"គន្លឹះ៖ ប្រមាណវិធីផ្ទុយអាចលុប {constant or 'ចំនួនថេរ'}។",
                    "stuck_task": f"តើប្រមាណវិធីណាអាចលុប {constant or 'ចំនួនថេរ'}?",
                    "different_spoken": "គិតដូចតុល្យភាព៖ ធ្វើដូចគ្នាលើទាំងសងខាង។",
                    "different_display": f"វិធីផ្សេង៖ ប្រើប្រមាណវិធីផ្ទុយលើ {constant or 'ចំនួនថេរ'}។",
                    "different_task": f"តើអ្វីលុប {constant or 'ចំនួនថេរ'}?",
                }
            return {
                **fallback_text,
                "default_spoken": f"Look at the constant {constant or ''}. What operation cancels it?",
                "default_display": f"Focus on the constant {constant or ''}. Use the inverse operation.",
                "default_task": f"What first operation should we use: {operation} or something else?",
                "stuck_spoken": f"That's okay. Focus only on the constant {constant or ''} first.",
                "stuck_display": f"Hint: the inverse operation cancels {constant or 'the constant'}.",
                "stuck_task": f"What operation cancels {constant or 'the constant'}?",
                "different_spoken": "Think of the equation like a balance scale: do the same move to both sides.",
                "different_display": f"Different view: use the opposite operation on {constant or 'the constant'}.",
                "different_task": f"What cancels {constant or 'the constant'}?",
            }
        if coefficient:
            return {
                **fallback_text,
                "default_task": f"What operation cancels the {coefficient} beside x?",
                "stuck_task": f"What operation separates x from {coefficient}?",
                "different_task": f"What inverse operation isolates x from {coefficient}?",
            }
    return fallback_text


def _subject_aware_fallback_text(
    understanding: VisualTutorProblemUnderstandingResult,
    *,
    use_khmer: bool,
    is_stuck: bool,
    explain_differently: bool,
) -> dict[str, str]:
    del is_stuck, explain_differently
    subject = understanding.subject.lower()
    problem_type = understanding.problem_type.lower()
    is_english = subject == "english" or problem_type.startswith("english_")
    is_khmer_subject = subject == "khmer" or problem_type.startswith("khmer_")
    is_concept = subject in {"physics", "chemistry"} or problem_type.endswith(
        "_concept_question"
    )

    if is_english:
        return {
            "stuck_spoken": "That's okay. Let's inspect one sentence choice at a time.",
            "stuck_display": "Small step: find the word or sentence part causing confusion.",
            "stuck_task": "Which sentence or grammar choice should we inspect first?",
            "different_spoken": "Let's switch views and compare two short examples.",
            "different_display": "Different view: compare the grammar choices in context.",
            "different_task": "Write the sentence or word pair you want to compare.",
            "default_spoken": "Let's treat this like a teacher would: one grammar choice first.",
            "default_display": "Start with the exact sentence or word choice.",
            "default_task": "Which sentence or grammar choice should we inspect first?",
        }

    if is_khmer_subject or use_khmer:
        return {
            "stuck_spoken": "មិនអីទេ យើងមើលតែមួយចំណុចសិន។",
            "stuck_display": "ជំហានតូច៖ រកពាក្យ ឃ្លា ឬគំនិតដែលធ្វើឱ្យច្រឡំ។",
            "stuck_task": "តើអ្នកចង់ឱ្យគ្រូពន្យល់ពាក្យ ឃ្លា ឬគំនិតមួយណាមុន?",
            "different_spoken": "យើងប្តូររបៀបពន្យល់ ហើយប្រើឧទាហរណ៍ខ្លីមួយ។",
            "different_display": "វិធីផ្សេង៖ ប្រៀបធៀបឧទាហរណ៍ខ្លីៗ។",
            "different_task": "សរសេរពាក្យ ឃ្លា ឬប្រយោគដែលអ្នកចង់ពិនិត្យ។",
            "default_spoken": "គ្រូនឹងចាប់ផ្តើមពីចំណុចតូចមួយសិន។",
            "default_display": "ចាប់ផ្តើមពីពាក្យ ឃ្លា ឬគំនិតសំខាន់។",
            "default_task": "តើអ្នកចង់ឱ្យគ្រូពន្យល់ពាក្យ ឃ្លា ឬគំនិតមួយណាមុន?",
        }

    if is_concept:
        return {
            "stuck_spoken": "That's okay. Let's focus on one concept piece first.",
            "stuck_display": "Small step: name the concept part that feels unclear.",
            "stuck_task": "Which part of this concept should we explain first?",
            "different_spoken": "Let's use a different visual example for the same concept.",
            "different_display": "Different view: connect the concept to a simple example.",
            "different_task": "Which part should we visualize first?",
            "default_spoken": "Let's ground this concept with one focused question.",
            "default_display": "Start with the main concept or formula.",
            "default_task": "Which part of this concept should we explain first?",
        }

    return {
        "stuck_spoken": "That's okay. Let's slow down and use one small step. What is the problem asking for?",
        "stuck_display": "Small step: identify what we need to find.",
        "stuck_task": "Tell me the value or idea we need to find.",
        "different_spoken": "Let's use a different view. Break the problem into small parts before solving.",
        "different_display": "Different view: separate what is given from what we need.",
        "different_task": "Write one piece of information the problem gives.",
        "default_spoken": "Let's inspect one useful part first, then we will decide the next step together.",
        "default_display": "Start with one focused observation.",
        "default_task": "Tell me what value we need to find, or write your first step.",
    }


def _fallback_interaction(
    student_task: str,
    understanding: VisualTutorProblemUnderstandingResult,
    *,
    policy: VisualTutorPolicyDecision,
    use_khmer: bool,
) -> VisualTutorInteraction:
    return VisualTutorInteraction(
        type=VisualTutorInteractionType.TEXT_RESPONSE,
        prompt=student_task,
        expected_answer_locked=policy.final_answer_locked,
        validation_strategy="student_input_understanding",
        input_enabled=True,
        submit_label="ឆ្លើយ" if use_khmer else "Submit",
        metadata={
            "planner": LLM_PLANNER_VERSION,
            "fallback_interaction": True,
            "problem_type": understanding.problem_type,
        },
    )


_LIMITS_BOARD_ACTION_EXAMPLES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "write_text",
        "write_text",
        {
            "id": "intro-text", "type": "write_text", "sequence_index": 0,
            "duration_ms": 400, "layout_zone": "problem", "layout_flow": "vertical",
            "text": "Let's see what f(x) approaches as x gets close to 1.",
        },
    ),
    (
        "write_equation",
        "write_equation",
        {
            "id": "problem-eq", "type": "write_equation", "sequence_index": 1,
            "duration_ms": 450, "layout_zone": "problem", "layout_flow": "vertical",
            "latex": "\\lim_{x \\to 1} \\frac{x^2 - 1}{x - 1}",
        },
    ),
    (
        "table_of_values",
        "show_table",
        {
            "id": "values-table", "type": "show_table", "sequence_index": 2,
            "duration_ms": 700, "width": 360, "height": 160,
            "layout_zone": "visual", "layout_flow": "vertical",
            "table": {
                "columns": ["x", "f(x)"],
                "rows": [["0.9", "1.9"], ["0.99", "1.99"], ["1.01", "2.01"], ["1.1", "2.1"]],
            },
        },
    ),
    (
        "function_graph_with_approach_arrows",
        "show_graph",
        {
            "id": "approach-graph", "type": "show_graph", "sequence_index": 3,
            "duration_ms": 900, "width": 420, "height": 300,
            "layout_zone": "visual", "layout_flow": "vertical",
            "graph": {
                "x_min": -1, "x_max": 3, "y_min": -1, "y_max": 5,
                "function_expression": "(x^2-1)/(x-1)",
                "points": [{"x": 1, "y": 2, "label": "target"}],
                "annotations": [
                    {"text": "x -> 1-", "x": 0.6, "y": 1.6},
                    {"text": "x -> 1+", "x": 1.4, "y": 2.4},
                ],
            },
        },
    ),
    (
        "ask_student_step",
        "student_task",
        {
            "id": "ask-limit-value", "type": "student_task", "sequence_index": 4,
            "duration_ms": 0, "layout_zone": "student_task", "layout_flow": "vertical",
            "text": "What value does f(x) approach as x gets closer to 1?",
            "requires_student_response": True,
        },
    ),
)


def _limits_board_action_shapes_block() -> str:
    """Concrete, closed-set board_action shapes for limit_of_function turns.

    The general instructions above describe the full cross-subject action
    type list abstractly (just names). For this scope-locked build that is
    the one topic every request will actually be, so give the model exact,
    copyable JSON instead of asking it to infer field shapes from a type
    name -- board_contract.py's VisualTutorBoardAction (and the matching
    VisualTutorCanvasAction) reject anything that doesn't match these
    fields exactly.
    """
    lines = [
        "LIMITS BOARD SHAPES: this is a Grade 12 limits-of-functions turn. "
        "The one PRIMARY VISUAL action in teaching_plan.board_actions, and its "
        "student_task, must come only from this closed set of five shapes -- do "
        "not invent other visual action types or extra fields for this topic. "
        "This closed set does not replace the required speak_marker/pause_marker "
        "wrapper described above -- board_actions must still be exactly "
        "[speak_marker, one shape from this set, student_task from this set, "
        "pause_marker]. Each example is valid JSON as-is; adapt the values "
        "(formula/table/graph numbers, text) to this specific problem, keep "
        "the field names and structure identical."
    ]
    for descriptive_name, real_type, example in _LIMITS_BOARD_ACTION_EXAMPLES:
        label = (
            f"{descriptive_name} (type: \"{real_type}\")"
            if descriptive_name != real_type
            else descriptive_name
        )
        lines.append(f"- {label}: {json.dumps(example, ensure_ascii=False)}")
    lines.append(
        "There is no separate \"arrow\" primitive for a graph: show the "
        "left/right approach as short text callouts in graph.annotations "
        "(as in the function_graph_with_approach_arrows example above), "
        "anchored at the x/y coordinates you want them to point near."
    )
    return " ".join(lines)


def _build_system_prompt(
    policy: VisualTutorPolicyDecision,
    current_step_index: Optional[int] = None,
    problem_type: Optional[str] = None,
) -> str:
    intent = policy.metadata.get("student_intent", "unknown")
    limits_shapes_instruction = (
        f" {_limits_board_action_shapes_block()}"
        if problem_type == "limit_of_function"
        else ""
    )
    state_aware_instruction = ""
    if current_step_index is not None and current_step_index > 0:
        state_aware_instruction = (
            f"SYSTEM: The student is currently viewing STEP {current_step_index} of the problem "
            f"on their visual whiteboard. Do NOT repeat previous steps. Answer their question "
            f"specifically contextualized to this step. Assess if they understand this current "
            f"step before deciding to advance to the next step. "
        )

    return (
        "You are a one-to-one AI visual tutor for Cambodian high school students. "
        "You behave like a real visual teacher: speak briefly, write or draw one useful idea, "
        "ask one question or give one small task, then wait. "
        f"{state_aware_instruction}"
        f"{limits_shapes_instruction}"
        "BOARD LAYOUT RULE (most important): The user prompt contains board_layout.next_y — "
        "this is the Y pixel position where you MUST start your first board_action. "
        "Every board_action after the first must have y >= previous_action.y + previous_action.height + 12. "
        "Never place any action at a y value lower than board_layout.next_y. "
        "Never overlap elements vertically. Always write top-to-bottom, left-to-right. "
        "This is non-negotiable: if you ignore board_layout.next_y, elements will overlap on screen. "
        "Return strict JSON only. Do not use markdown. Do not write prose outside the JSON object. "
        "The JSON must contain these legacy compatibility fields: spoken_text, display_text, "
        "teaching_mode, student_task, board, canvas_actions, mastery_signal, metadata. "
        "It must also contain these live frontend fields: screen_state, tutor_status, "
        "speech, board_actions, interaction, quick_actions. "
        "It may also contain teaching_stage, teaching_board, and allowed_actions. "
        "It must contain teaching_plan: a JSON object with schema_version=1, representation, "
        "learning_objective, teaching_message, board_actions, allowed_student_actions, "
        "hidden_answer_policy, and next_state_policy. "
        "teaching_message is read aloud and shown TO the student, so write it to them in second person "
        "(\"What do you get when you factor x² − 9?\"); never refer to \"the student\" and never phrase it "
        "as an instruction to the tutor (\"Ask the student to...\"). learning_objective is the internal goal "
        "and may be phrased about the student. "
        "hidden_answer_policy and next_state_policy are JSON OBJECTS, never plain strings. "
        "hidden_answer_policy must look exactly like this shape: "
        "{\"mode\": \"hidden\", \"deterministic_policy_permits_final_reveal\": false} -- "
        "mode is one of hidden, partial, reveal_allowed; deterministic_policy_permits_final_reveal is true or false. "
        "next_state_policy must look exactly like this shape: "
        "{\"correct\": \"continue\", \"invalid\": \"ask_for_work\", \"incomplete\": \"ask_for_work\", "
        "\"stuck\": \"reteach\", \"hint\": \"continue\", \"explain_differently\": \"reteach\"} -- "
        "it must have exactly these six keys (correct, invalid, incomplete, stuck, hint, explain_differently), "
        "each set to one of: continue, reteach, ask_for_work, offer_practice, reveal_progressively, unsupported_recovery. "
        "teaching_plan.representation must be one of: "
        "equation_transformation, balance_scale, worked_example, number_line, coordinate_graph, "
        "table, conceptual_explanation, error_analysis, free_body_diagram, wave_diagram, molecule_diagram, circuit_diagram. "
        "Its board_actions must use only: write_text, "
        "write_equation, transform_equation, highlight, cross_out, draw_rectangle, circle, draw_arrow, draw_point, show_hint, "
        "show_feedback, student_task, show_number_line, draw_axes, show_graph, plot_function, "
        "graph_annotation, show_table, fade_previous, speak_marker, pause_marker, final_answer_reveal, "
        "draw_free_body_diagram, draw_molecule, draw_wave. "
        "For draw_free_body_diagram: metadata must include object_label (string) and forces (array of {direction: up|down|left|right, label: string, magnitude: 0.5-2.0}). "
        "For draw_molecule: metadata must include atoms (array of {symbol: string, x: 0-1, y: 0-1}) and bonds (array of {from: int, to: int, order: 1|2|3}). "
        "For draw_wave: metadata must include cycles (number), amplitude_label (string), wavelength_label (string). "
        "Use draw_free_body_diagram for force/mechanics problems. Use draw_molecule for chemistry problems. Use draw_wave for wave/sound/light physics. "
        "Use only bounded numeric geometry; "
        "number lines require {min,max,step,labels}; tables require {columns,rows}; labels are plain text. "
        "teaching_plan.board_actions must contain, IN THIS ORDER: (1) one speak_marker, (2) exactly one primary "
        "visual action, (3) exactly one student_task action, (4) one pause_marker. That student_task action is "
        "the \"exactly one visible student_task\" this turn needs -- it goes in teaching_plan.board_actions itself, "
        "never only in the separate legacy top-level student_task string field. student_task example: "
        "{\"id\": \"task-1\", \"type\": \"student_task\", \"sequence_index\": 2, \"duration_ms\": 0, "
        "\"layout_zone\": \"student_task\", \"layout_flow\": \"vertical\", \"text\": \"<your one question here>\", "
        "\"requires_student_response\": true}. "
        "The ONLY exception: when server policy authorizes a full final-answer reveal for this turn, replace step "
        "(3) with one final_answer_reveal action instead of a student_task -- never send both, and never send "
        "neither. teaching_plan.board_actions with zero student_task AND zero final_answer_reveal actions is "
        "always rejected. "
        "speak_marker and pause_marker are timing-only actions -- they have NO text field at all, do not add "
        "text: \"\" or any other field to them. speak_marker example: "
        "{\"id\": \"speak-1\", \"type\": \"speak_marker\", \"sequence_index\": 0, \"duration_ms\": 0}. "
        "pause_marker example: {\"id\": \"pause-1\", \"type\": \"pause_marker\", \"sequence_index\": 3, \"duration_ms\": 700}. "
        "speak_marker.duration_ms=0; "
        "pause_marker.duration_ms must be 500-900. Set the primary visual duration_ms to 350-500 for text/equations, "
        "450-650 for shapes/arrows, 650-800 for number lines/tables, and 800-1000 for graphs. "
        "Use at most one highlight and target that primary visual only. Use fade_previous only when older work distracts. "
        "Never include code, URLs, HTML, CSS, SVG, widget names, or executable content. "
        "Only use final_answer_reveal when server policy permits a final reveal. "
        "screen_state must be one of: speaking_writing, asking_question, graph_based, "
        "check_my_work, final_verified_answer, unsupported_problem. "
        "Use unsupported_problem only for an intentional friendly unsupported screen; otherwise "
        "unsupported math should still get a helpful speaking_writing or asking_question turn. "
        "Do not include final_answer_locked. The server policy decides it. "
        "Generate only the next teacher action, never a lesson page or full lesson. "
        "Act like a real one-to-one teacher: infer what the student needs now, "
        "then respond with one short speech, one focused visual idea, and one student interaction. "
        "Write on the canvas first: board_actions must be visual and useful, not decorative filler. Prefer a graph or axes "
        "for coordinate relationships, a number line for ordered values/inequalities, a transformation for equation steps, "
        "and a diagram or table when it makes the idea clearer than prose. "
        "Use board_actions for the live teaching stage "
        "and canvas_actions for backward compatibility. Add exactly one focused visual action group per turn. "
        "Do not dump notes, a complete solution, or multiple lesson sections onto the canvas. "
        "Ask one question or give one small task, then wait for the student. "
        "Use solver_facts as the correctness source for expected steps, validation, known safe formulas, "
        "verified answers, and mistake diagnosis. Do not contradict solver_facts. "
        "Teach Socratically: ask guiding questions, give hints, and avoid direct final answers unless policy allows. "
        "Do not generate arbitrary code, Flutter code, SVG code, HTML, JavaScript, or drawing functions. "
        "Do not return markdown-only answers, markdown code fences, prose outside JSON, or a single markdown solution. "
        f"Policy final_answer_locked={policy.final_answer_locked}. "
        f"Policy partial_solution_allowed={policy.partial_solution_allowed}. "
        f"Policy full_solution_allowed={policy.full_solution_allowed}. "
        f"Policy request_student_step={policy.request_student_step}. "
        f"Policy give_hint={policy.give_hint}. "
        f"Policy diagnose_misconception={policy.diagnose_misconception}. "
        f"Policy reveal_final={policy.reveal_final}. "
        f"Student intent={intent}. "
        "If student intent is stuck, reteach the current step with a simpler visual, "
        "ask exactly one guiding question, and do not grade the stuck message as a step. "
        "If the student input is wrong or unrelated, highlight only the first mistake or mismatch, "
        "explain it briefly, and redirect to the current board focus. "
        "If student intent is request_explain_differently, use a different analogy or representation, "
        "then ask one short guiding question. "
        "If Khmer is requested by policy, use Khmer-friendly wording suitable for Cambodian high school students. "
        "Keep each teacher prompt supportive, age-appropriate, and no longer than two short sentences. "
        "If curriculum_context is provided, use it only to ground explanations, formulas, prerequisites, "
        "Khmer terms, and misconceptions. Do not copy worked example answers or exercise answers. "
        "For graph, scatter plot, or regression prompts, make board_actions visual: draw_axes, draw_point, "
        "draw_line, show_table, draw_graph_hint, highlight, or write_equation as appropriate. "
        "If reveal_final is false, do not reveal final answers, roots, solved values, or complete solutions. "
        "If reveal_final is false, canvas_actions must not contain final answers in text or latex. "
        "If reveal_final is true, reveal the answer progressively as teaching actions, not as one static page. "
        "If a future or final step is useful to plan, mark it locked=true, type=hide, "
        "reveal_policy='final_answer_unlocked', and do not include the answer text. "
        "When final_answer_locked is true, board items may show setup, known facts, formulas, "
        "or one partial step only if partial_solution_allowed is true. "
        "board_actions and canvas_actions must be arrays of objects with fields: id, type, x, y, width, height, "
        "text, latex, points, target_id, style, locked, reveal_policy, metadata. "
        "Allowed canvas action types: write_text, write_equation, draw_line, draw_arrow, draw_point, "
        "draw_axes, draw_graph_hint, highlight, erase, focus, reveal, hide, speak_marker, pause_marker. "
        "Use only these validated action types. Use write_text for short teacher notes, write_equation for formulas/equations, "
        "highlight to focus the current step, speak_marker before the visible step, and pause_marker after it. "
        "For Khmer or bilingual mode, use only approved_glossary_terms supplied by the curriculum context. "
        "Never use raw khmer_terms or invent a translation. Keep equations, units, symbols, variables, and chemical notation unchanged. "
        "In bilingual mode, write the approved Khmer term first with one concise English gloss only on its first lesson use; thereafter use only the selected Khmer term. "
        "For each glossary_gaps term, retain the English term without a Khmer translation. "
        "Board must be an object with type, title, items, and metadata. "
        "quick_actions must use only: submit_answer, request_hint, explain_differently, "
        "show_visually, check_work, request_answer, stuck. "
        "Use board.type from: equation, equation_steps, formula_card, graph_hint, "
        "table, coordinate_points, word_problem_breakdown, misconception_card. "
        "Use teaching_mode from: greeting, diagnose_problem, guided_question, hint, "
        "step_check, partial_solution, full_solution, misconception_fix, stuck_help. "
        "Use mastery_signal from: exploring, needs_hint, misconception, improving, "
        "ready_for_next_step, mastered. "
        "teaching_move_instruction.move is the exact teaching action you must execute this turn. "
        "Do not deviate from it. Do not choose a different pedagogy. "
        "student_model describes the current learner state. "
        "recommended_depth=simple means use shorter sentences and more visual analogies. "
        "If hint_level >= 2, be warmer and more encouraging. Do not penalize slow progress. "
        "If recent_mistakes is non-empty, the most recent entry is the highest priority mistake "
        "to address in your current teaching action. "
        "If wrong_attempt_streak >= 3, do not request another step attempt — reteach with a "
        "simpler approach instead. "
        "If preferred_language is km, use Khmer for all student-facing text. "
        "strategy_history describes recent teaching moves, interaction types, mistakes addressed, "
        "and whether the tutor asked for another attempt. Use it to avoid repeating the same "
        "teaching pattern when the student is stuck or making repeated mistakes. "
        "If strategy_history shows recent show_visual_hint, explain differently with a new analogy "
        "or simpler decomposition instead of replaying the same visual. "
        "If strategy_history shows recent reteach_differently, use a focused visual hint if policy "
        "allows visual work. "
        "Do not expose student_model or strategy_history contents in spoken_text or display_text."
    )


def _compute_board_next_y(visible_board_elements: object) -> float:
    """Compute the Y position where the next board action should start writing.

    The AI must write top-to-bottom like a real teacher. We compute the bottom
    of the last visible element on the board and return it as the starting Y
    for the next action group. If the board is empty we start at 40.
    """
    if not isinstance(visible_board_elements, list):
        return 40.0
    bottom = 0.0
    for element in visible_board_elements:
        if not isinstance(element, dict):
            continue
        if element.get("hidden"):
            continue
        y = element.get("y")
        height = element.get("height")
        if isinstance(y, (int, float)) and isinstance(height, (int, float)):
            fy, fh = float(y), float(height)
            if math.isfinite(fy) and math.isfinite(fh):
                fy = max(0.0, min(fy, 5000.0))
                fh = max(0.0, min(fh, 5000.0))
                element_bottom = fy + fh
                if element_bottom > bottom:
                    bottom = element_bottom
    # Add 18px gap between teaching blocks (same gap as Flutter fallback layout)
    return max(40.0, bottom + 18.0) if bottom > 0 else 40.0


def _build_user_prompt(
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
    policy: VisualTutorPolicyDecision,
    *,
    student_model: Optional[dict] = None,
    strategy_history: Optional[list[dict[str, Any]]] = None,
) -> str:
    adaptive_tutor_decision = policy.metadata.get("adaptive_tutor_decision", {})
    if not isinstance(adaptive_tutor_decision, dict):
        adaptive_tutor_decision = {}

    # Compute where the AI should start writing on the board for this turn.
    # This is the single most important layout signal we give the LLM — without
    # it, every turn overlaps previous content at hardcoded positions.
    visible_board_elements = request.metadata.get("visible_board_elements") or []
    board_next_y = _compute_board_next_y(visible_board_elements)
    board_is_empty = len([
        e for e in visible_board_elements
        if isinstance(e, dict) and not e.get("hidden")
    ]) == 0

    return json.dumps(
        {
            "student_message": request.message,
            "subject": request.subject,
            "topic": request.topic,
            "action": request.action,
            "student_intent": policy.metadata.get("student_intent", "unknown"),
            "stuck_reason": policy.metadata.get("stuck_reason"),
            "current_state": request.current_state.model_dump(mode="json"),
            "problem_understanding": understanding.model_dump(mode="json"),
            "solver_facts": policy.metadata.get("solver_facts"),
            "student_model": student_model,
            "board_layout": {
                "next_y": board_next_y,
                "board_is_empty": board_is_empty,
                "visible_element_count": len([
                    e for e in visible_board_elements
                    if isinstance(e, dict) and not e.get("hidden")
                ]),
                "instruction": (
                    f"IMPORTANT: Place your first board_action at y={board_next_y:.0f} (or higher if needed). "
                    "Each subsequent action in board_actions must have a y value at least (previous_y + previous_height + 12). "
                    f"Never place any action at y less than {board_next_y:.0f}. "
                    "Write top-to-bottom like a teacher filling a whiteboard page. "
                    "x=28 for normal content, x=48 for indented sub-steps. "
                    "Standard widths: text=660, equation=500, diagram=600. "
                    "Standard heights: text=44, equation=52, graph=200, table=150, number_line=80."
                    if not board_is_empty else
                    f"Board is empty. Start at y=40. x=28 for normal content. "
                    "Each next action goes at y = previous_y + previous_height + 12. "
                    "Standard widths: text=660, equation=500, diagram=600. "
                    "Standard heights: text=44, equation=52, graph=200, table=150, number_line=80."
                ),
            },
            "strategy_history": strategy_history,
            "adaptive_tutor_decision": policy.metadata.get("adaptive_tutor_decision"),
            "teaching_move_instruction": {
                "move": policy.metadata.get("tutor_move", "teach_next_visual_step"),
                "reason_code": adaptive_tutor_decision.get("reason"),
                "board_budget": adaptive_tutor_decision.get("board_action_budget", 2),
                "interaction_type": adaptive_tutor_decision.get(
                    "interaction_type", "text_response"
                ),
                "answer_lock_decision": adaptive_tutor_decision.get(
                    "answer_lock_decision", "lock_final_answer"
                ),
            },
            "planner_inputs": policy.metadata.get("planner_inputs"),
            "policy": {
                "teaching_mode": policy.teaching_mode,
                "final_answer_locked": policy.final_answer_locked,
                "reveal_final": policy.reveal_final,
                "reveal_partial": policy.reveal_partial,
                "partial_solution_allowed": policy.partial_solution_allowed,
                "full_solution_allowed": policy.full_solution_allowed,
                "request_student_step": policy.request_student_step,
                "give_hint": policy.give_hint,
                "diagnose_misconception": policy.diagnose_misconception,
                "should_ask_question": policy.should_ask_question,
                "use_khmer_explanation": policy.use_khmer_explanation,
                "student_intent": policy.metadata.get("student_intent", "unknown"),
                "stuck_reason": policy.metadata.get("stuck_reason"),
                "reason": policy.reason,
            },
            "curriculum_context": _curriculum_prompt_context(policy),
            "canvas_action_schema": _canvas_action_prompt_schema(),
            "live_teaching_stage_schema": _live_teaching_stage_prompt_schema(),
            "planner_instruction": _intent_planner_instruction(policy),
        },
        ensure_ascii=False,
    )


def _curriculum_prompt_context(policy: VisualTutorPolicyDecision) -> dict[str, Any]:
    context = policy.metadata.get("curriculum_context")
    if not isinstance(context, list):
        context = []
    safe_context = []
    for chunk in context[:3]:
        if not isinstance(chunk, dict):
            continue
        safe_context.append(
            {
                "id": chunk.get("id"),
                "grade": chunk.get("grade"),
                "subject": chunk.get("subject"),
                "topic": chunk.get("topic"),
                "subtopic": chunk.get("subtopic"),
                "content_type": chunk.get("content_type"),
                "text": chunk.get("text"),
                "formulas": chunk.get("formulas") or [],
                "prerequisites": chunk.get("prerequisites") or [],
                "common_misconceptions": chunk.get("common_misconceptions") or [],
                "teaching_sequence": chunk.get("teaching_sequence") or [],
                "khmer_terms": chunk.get("khmer_terms") or {},
                "source": chunk.get("source") or {},
            }
        )

    return {
        "chunks": safe_context,
        "chunk_ids": policy.metadata.get("curriculum_chunk_ids") or [],
        "confidence": policy.metadata.get("curriculum_confidence", 0.0),
        "formulas": policy.metadata.get("formulas") or [],
        "prerequisites": policy.metadata.get("prerequisites") or [],
        "common_misconceptions": (policy.metadata.get("common_misconceptions") or []),
        "teaching_sequence": policy.metadata.get("teaching_sequence") or [],
        "khmer_terms": policy.metadata.get("khmer_terms") or {},
        "sources": policy.metadata.get("curriculum_sources") or [],
        "usage_rules": [
            "Use curriculum only for explanation and grounding.",
            "Do not reveal final answers when policy.final_answer_locked is true.",
            "Do not include worked example answers or exercise answers.",
            "Prefer khmer_terms when policy.use_khmer_explanation is true.",
            "Use a Khmer technical term only when it appears in khmer_terms; otherwise keep the English term and mark glossary_gap for curriculum review. Never invent a translation.",
            "For bilingual mode, give Khmer first then a concise English gloss; keep equations and symbols unchanged.",
        ],
    }


def _fallback_board(
    understanding: VisualTutorProblemUnderstandingResult,
    policy: Optional[VisualTutorPolicyDecision] = None,
) -> VisualTutorBoard:
    board_type = (
        understanding.recommended_board_type or VisualTutorBoardType.FORMULA_CARD
    )
    intent = (policy.metadata.get("student_intent") if policy else None) or "unknown"
    items = [
        VisualTutorBoardItem(
            label="Problem",
            content=understanding.extracted_problem,
            status="active",
        )
    ]
    focus_text = _fallback_focus_text(understanding, policy=policy)
    if intent == "stuck":
        items.append(
            VisualTutorBoardItem(
                label="Focus",
                content=focus_text,
                status="active",
            )
        )
    elif intent == "request_explain_differently":
        items.append(
            VisualTutorBoardItem(
                label="Different view",
                content=(
                    "Separate given information from the unknown."
                    if understanding.language != "km"
                    else "បំបែកព័ត៌មានដែលបានឱ្យ និងអ្វីដែលត្រូវរក។"
                ),
                status="active",
            )
        )
    return VisualTutorBoard(
        type=board_type,
        title=understanding.topic or "Visual Tutor",
        items=items,
        metadata={
            "problem_type": understanding.problem_type,
            "known_solver_available": understanding.known_solver_available,
            "student_intent": intent,
        },
    )


def _parse_canvas_actions(value: Any) -> list[VisualTutorCanvasAction]:
    if not isinstance(value, list):
        return []
    actions: list[VisualTutorCanvasAction] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        try:
            actions.append(VisualTutorCanvasAction.model_validate(item))
        except ValidationError:
            actions.append(
                VisualTutorCanvasAction(
                    id=f"llm-invalid-canvas-action-{index}",
                    type="write_text",
                    x=40,
                    y=80 + index * 56,
                    text=str(
                        item.get("text")
                        or item.get("latex")
                        or "Look at the current step."
                    ),
                    metadata={
                        "planner": LLM_PLANNER_VERSION,
                        "invalid_canvas_action_recovered": True,
                    },
                )
            )
    return actions


def _limit_to_one_visual_group(actions: list[Any]) -> list[Any]:
    """Keep one teaching moment from LLM output while preserving timing markers."""
    if not actions:
        return []

    marker_types = {
        VisualTutorCanvasActionType.SPEAK_MARKER,
        VisualTutorCanvasActionType.PAUSE_MARKER,
    }
    primary_group = None
    for action in actions:
        if action.type in marker_types:
            continue
        primary_group = _action_group_id(action)
        break

    if not primary_group:
        return actions

    focused: list[Any] = []
    removed_count = 0
    for action in actions:
        action_group = _action_group_id(action)
        if action.type in marker_types or action_group in {primary_group, None}:
            focused.append(action)
        else:
            removed_count += 1

    if removed_count:
        focused = [
            (
                action.model_copy(
                    update={
                        "metadata": {
                            **action.metadata,
                            "llm_visual_group_trimmed": removed_count,
                        }
                    }
                )
                if index == 0
                else action
            )
            for index, action in enumerate(focused)
        ]
    return focused


def _action_group_id(action: Any) -> str | None:
    metadata = action.metadata if isinstance(action.metadata, dict) else {}
    return (
        getattr(action, "group_id", None)
        or metadata.get("group_id")
        or metadata.get("visual_group")
        or metadata.get("section_id")
    )


def _repair_action_style(item: dict) -> dict:
    """Drop a `style` the model wrote as a label instead of an object.

    DeepSeek reliably emits `"style": "task"` / `"timing"` / `"normal"` where
    the board contract expects a CanvasElementStyle object. That single type
    mismatch used to invalidate the whole action, so a usable instruction like
    "Try substituting x = 3" was thrown away and replaced by placeholder text.
    The field defaults to a CanvasElementStyle, so removing a malformed one
    costs only cosmetic styling and keeps the teaching content.
    """
    if isinstance(item.get("style"), dict):
        return item
    return {key: value for key, value in item.items() if key != "style"}


def _parse_board_actions(value: Any) -> list[VisualTutorBoardAction]:
    if not isinstance(value, list):
        return []
    actions: list[VisualTutorBoardAction] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        try:
            actions.append(VisualTutorBoardAction.model_validate(_repair_action_style(item)))
        except ValidationError as exc:
            # Previously silent, which is why planner drift showed up only as
            # "Look at the current step." on a student's board with nothing in
            # any log to explain it.
            logger.warning(
                "visual_tutor board action rejected index=%s errors=%s",
                index,
                exc.errors()[:3],
            )
            actions.append(
                VisualTutorBoardAction(
                    id=f"llm-invalid-board-action-{index}",
                    type="write_text",
                    sequence_index=index,
                    x=40,
                    y=80 + index * 56,
                    text=str(
                        item.get("text")
                        or item.get("latex")
                        or "Look at the current step."
                    ),
                    metadata={
                        "planner": LLM_PLANNER_VERSION,
                        "invalid_board_action_recovered": True,
                    },
                )
            )
    return actions


def _parse_speech(
    value: Any,
    *,
    fallback_text: str,
    policy: VisualTutorPolicyDecision,
) -> Optional[VisualTutorSpeech]:
    if not isinstance(value, dict):
        return None
    try:
        return VisualTutorSpeech.model_validate(value)
    except ValidationError:
        return VisualTutorSpeech(
            text=fallback_text,
            language="km" if policy.use_khmer_explanation else "en",
            metadata={
                "planner": LLM_PLANNER_VERSION,
                "invalid_speech_recovered": True,
            },
        )


def _parse_teaching_stage(value: Any) -> Optional[VisualTutorTeachingStage]:
    if not isinstance(value, dict):
        return None
    try:
        return VisualTutorTeachingStage.model_validate(value)
    except ValidationError:
        return None


def _parse_teaching_board(value: Any) -> Optional[TeachingBoardState]:
    if not isinstance(value, dict):
        return None
    try:
        return TeachingBoardState.model_validate(value)
    except ValidationError:
        return None


def _parse_interaction(value: Any) -> Optional[VisualTutorInteraction]:
    if not isinstance(value, dict):
        return None
    try:
        return VisualTutorInteraction.model_validate(value)
    except ValidationError:
        return None


def _parse_allowed_actions(value: Any) -> list[VisualTutorAllowedAction]:
    if not isinstance(value, list):
        return []
    actions: list[VisualTutorAllowedAction] = []
    for item in value:
        try:
            actions.append(VisualTutorAllowedAction(item))
        except Exception:
            continue
    return actions


def _parse_screen_state(value: Any) -> Optional[VisualTutorScreenState]:
    try:
        return VisualTutorScreenState(value)
    except Exception:
        return None


def _default_allowed_actions() -> list[VisualTutorAllowedAction]:
    return [
        VisualTutorAllowedAction.SUBMIT_ANSWER,
        VisualTutorAllowedAction.REQUEST_HINT,
        VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
        VisualTutorAllowedAction.SHOW_VISUALLY,
        VisualTutorAllowedAction.STUCK,
    ]


def _fallback_canvas_actions(
    understanding: VisualTutorProblemUnderstandingResult,
    *,
    policy: Optional[VisualTutorPolicyDecision] = None,
) -> list[VisualTutorCanvasAction]:
    use_khmer = (
        policy.use_khmer_explanation if policy else understanding.language == "km"
    )
    title = understanding.topic or "Visual Tutor"
    problem = understanding.extracted_problem
    focus = _fallback_focus_text(understanding, policy=policy)
    return [
        VisualTutorCanvasAction(
            id="llm-fallback-speak",
            type="speak_marker",
            metadata={"planner": LLM_PLANNER_VERSION},
        ),
        VisualTutorCanvasAction(
            id="llm-fallback-problem",
            type="write_text",
            x=40,
            y=40,
            width=620,
            height=48,
            text=problem,
            metadata={"title": title, "current_step": False},
        ),
        VisualTutorCanvasAction(
            id="llm-fallback-focus",
            type="write_text",
            x=40,
            y=104,
            width=620,
            height=48,
            text=focus,
            metadata={"current_step": True},
        ),
        VisualTutorCanvasAction(
            id="llm-fallback-highlight",
            type="highlight",
            target_id="llm-fallback-focus",
            x=34,
            y=98,
            width=640,
            height=60,
            metadata={"reason": "current_step"},
        ),
        VisualTutorCanvasAction(
            id="llm-fallback-pause",
            type="pause_marker",
            metadata={"duration_ms": 250},
        ),
    ]


def _fallback_board_actions(
    understanding: VisualTutorProblemUnderstandingResult,
    *,
    policy: Optional[VisualTutorPolicyDecision] = None,
    prompt: Optional[str] = None,
) -> list[VisualTutorBoardAction]:
    use_khmer = (
        policy.use_khmer_explanation if policy else understanding.language == "km"
    )
    focus = _fallback_focus_text(understanding, policy=policy)
    task = prompt or (
        "តើអ្នកឃើញព័ត៌មានសំខាន់មួយណា?"
        if use_khmer
        else "What important information do you notice first?"
    )
    uid = uuid.uuid4().hex[:8]
    return [
        VisualTutorBoardAction(
            id=f"fallback-speak-{uid}",
            type=VisualTutorCanvasActionType.SPEAK_MARKER,
            sequence_index=0,
            duration_ms=0,
            metadata={"planner": LLM_PLANNER_VERSION, "fallback": True},
        ),
        VisualTutorBoardAction(
            id=f"fallback-problem-{uid}",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=1,
            duration_ms=650,
            x=40,
            y=64,
            width=620,
            height=56,
            text=understanding.extracted_problem,
            metadata={
                "planner": LLM_PLANNER_VERSION,
                "fallback": True,
                "current_step": False,
                "group_id": f"fallback-{uid}",
            },
        ),
        VisualTutorBoardAction(
            id=f"fallback-focus-{uid}",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=2,
            duration_ms=650,
            x=40,
            y=132,
            width=620,
            height=56,
            text=focus,
            metadata={
                "planner": LLM_PLANNER_VERSION,
                "fallback": True,
                "current_step": True,
                "group_id": f"fallback-{uid}",
            },
        ),
        VisualTutorBoardAction(
            id=f"fallback-highlight-{uid}",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=3,
            duration_ms=250,
            target_id=f"fallback-focus-{uid}",
            metadata={
                "planner": LLM_PLANNER_VERSION,
                "fallback": True,
                "reason": "current_step",
                "group_id": f"fallback-{uid}",
            },
        ),
        VisualTutorBoardAction(
            id=f"fallback-task-{uid}",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=4,
            duration_ms=650,
            x=40,
            y=204,
            width=620,
            height=56,
            text=task,
            metadata={
                "planner": LLM_PLANNER_VERSION,
                "fallback": True,
                "current_step": True,
                "group_id": f"fallback-{uid}",
            },
        ),
    ]


def _fallback_focus_text(
    understanding: VisualTutorProblemUnderstandingResult,
    *,
    policy: Optional[VisualTutorPolicyDecision] = None,
) -> str:
    use_khmer = (
        policy.use_khmer_explanation if policy else understanding.language == "km"
    )
    subject = understanding.subject.lower()
    problem_type = understanding.problem_type.lower()
    if subject == "english" or problem_type.startswith("english_"):
        return "Write the exact sentence or grammar choice to inspect."
    if subject == "khmer" or problem_type.startswith("khmer_") or use_khmer:
        return "សរសេរពាក្យ ឃ្លា ឬគំនិតដែលចង់ឱ្យគ្រូពន្យល់។"
    if subject in {"physics", "chemistry"} or problem_type.endswith(
        "_concept_question"
    ):
        return "Choose the concept part or formula to inspect first."
    return (
        "ចាប់ផ្តើមដោយរកអ្វីដែលលំហាត់សួរ។"
        if use_khmer
        else "Start with one focused observation."
    )


def _canvas_action_prompt_schema() -> dict[str, Any]:
    return {
        "required": [
            "id",
            "type",
            "x",
            "y",
            "width",
            "height",
            "text",
            "latex",
            "points",
            "target_id",
            "style",
            "locked",
            "reveal_policy",
            "metadata",
        ],
        "types": [
            "write_text",
            "write_equation",
            "draw_line",
            "draw_arrow",
            "draw_point",
            "draw_axes",
            "draw_graph_hint",
            "highlight",
            "erase",
            "focus",
            "reveal",
            "hide",
            "speak_marker",
            "pause_marker",
        ],
        "rules": [
            "Use one small visual step per tutor turn.",
            "COORDINATE RULE: Start first action at y=board_layout.next_y. Each next action: y = prev_y + prev_height + 12.",
            "NEVER place any action at y less than board_layout.next_y. Never overlap elements.",
            "Use x=28 for normal content, x=48 for indented sub-steps.",
            "Standard dimensions: text h=44 w=660, equation h=52 w=500, graph h=200 w=600, table h=150 w=620, number_line h=80 w=600.",
            "Include speak_marker before the one primary visual and pause_marker after it.",
            "Use duration_ms: 350-500 text/equation, 450-650 shapes, 650-800 number line/table, 800-1000 graph; pause is 500-900.",
            "Use at most one highlight and target only the current primary visual; fade old work only when it distracts.",
            "Prefer a diagram, number line, graph, or equation transformation when it explains the idea better than text.",
            "Never include final answer text/latex unless policy.reveal_final is true.",
            "Future or final steps must be locked and hidden until policy allows.",
        ],
    }


def _live_teaching_stage_prompt_schema() -> dict[str, Any]:
    return {
        "required_response_fields": [
            "screen_state",
            "tutor_status",
            "speech",
            "board",
            "board_actions",
            "interaction",
            "quick_actions",
            "metadata",
        ],
        "screen_state": [
            "speaking_writing",
            "asking_question",
            "graph_based",
            "check_my_work",
            "final_verified_answer",
            "unsupported_problem",
        ],
        "tutor_status": "Writing... | Explaining | Waiting for you | Checking | Verified",
        "speech": {
            "text": "short teacher speech",
            "language": "en or km",
            "tts_status": "not_requested",
            "speak_after_action_id": "optional board action id",
            "pause_after_ms": 0,
        },
        "teaching_stage": {
            "stage_state": (
                "listening | analyzing | speaking | drawing | "
                "waiting_for_student | evaluating | adapting"
            ),
            "lesson_state": (
                "understand_request | instant_help | check_student_knowledge | "
                "teach | ask | evaluate | reteach_or_continue | verify | complete"
            ),
            "current_focus": "current board element id or concept",
            "turn_goal": "one concise goal for this turn",
            "max_actions_before_wait": 1,
        },
        "board_actions": _canvas_action_prompt_schema(),
        "interaction": {
            "type": (
                "text_response | voice_response | numeric_input | multiple_choice | "
                "fill_blank | yes_no | confidence | select_board_element | "
                "tap_incorrect_step | arrange_steps"
            ),
            "prompt": "one short question for the student",
            "expected_answer_locked": True,
            "validation_strategy": "optional deterministic validation hint",
            "choices": [],
            "input_enabled": True,
            "submit_label": "Submit",
        },
        "allowed_actions": [
            "submit_answer",
            "request_hint",
            "explain_differently",
            "show_visually",
            "check_work",
            "request_answer",
            "stuck",
        ],
        "quick_actions": [
            "submit_answer",
            "request_hint",
            "explain_differently",
            "show_visually",
            "check_work",
            "request_answer",
            "stuck",
        ],
        "rules": [
            "Return only the next turn.",
            "One speech, one visual idea, one interaction.",
            "Do not include arbitrary code.",
            "Final answer unlock is policy-only.",
            "Do not return markdown-only answers or prose outside the JSON object.",
            "Use unsupported_problem only for an intentional friendly unsupported screen.",
        ],
    }


def _intent_planner_instruction(policy: VisualTutorPolicyDecision) -> str:
    intent = policy.metadata.get("student_intent")
    if intent == "stuck":
        return (
            "Student is stuck. Give a simpler explanation, one concrete hint, "
            "a supportive board focused on the current step, and one guiding question. "
            "Do NOT reset the teaching plan. Stay on the current step."
        )
    if intent == "request_explain_differently":
        return (
            "Student wants a different explanation. Use a different representation "
            "or analogy, keep text concise, and ask one guiding question. "
            "Do NOT reset the teaching plan. Stay on the current step."
        )
    if intent == "clarifying_question":
        return (
            "Student asked a clarifying question. Answer it directly and concisely. "
            "Do NOT reset or advance the teaching plan. Stay exactly on the current step."
        )
    return (
        "Ask a guiding question before giving solution steps. "
        "Only advance the step if the student has demonstrated understanding of the current step."
    )


def _lock_final_answer_board(board: VisualTutorBoard) -> VisualTutorBoard:
    locked_items = []
    for item in board.items:
        label = item.label.lower()
        status = item.status.lower()
        content = item.content
        should_lock = (
            "final" in label
            or "answer" in label
            or "solution" in label
            or status == "final"
            or _contains_final_answer(content)
        )
        locked_items.append(
            VisualTutorBoardItem(
                label=item.label,
                content=(
                    "Locked until the student tries a step."
                    if should_lock
                    else _lock_final_answer_text(content)
                ),
                status="locked" if should_lock else item.status,
                metadata={**item.metadata, "final_answer_locked": should_lock},
            )
        )
    return VisualTutorBoard(
        type=board.type,
        title=board.title,
        items=locked_items,
        metadata={**board.metadata, "final_answer_locked": True},
    )


def _lock_final_answer_text(text: str) -> str:
    locked = _FINAL_ANSWER_RE.sub("Final answer is locked for now", text)
    locked = _VARIABLE_ANSWER_RE.sub("[locked answer]", locked)
    return locked


def _contains_final_answer(text: str) -> bool:
    return bool(_FINAL_ANSWER_RE.search(text) or _VARIABLE_ANSWER_RE.search(text))


def _mastery_signal(value: Any) -> VisualTutorMasterySignal:
    try:
        return VisualTutorMasterySignal(value)
    except Exception:
        return VisualTutorMasterySignal.EXPLORING
