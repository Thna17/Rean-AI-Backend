"""Live smoke test: one real round trip to DeepSeek through the Visual Tutor client.

Run:
    python scripts/smoke_test_deepseek_visual_tutor.py

Exits non-zero if DEEPSEEK_API_KEY is missing, the request fails, or the
response isn't valid JSON -- so a passing run is real proof the fixed model
id (see llm_teaching_planner.py:DeepSeekVisualTutorLLMClient) actually works
against the live API, not just against a mock.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

# Load ai-service/.env the same way api.core.config does, without requiring
# the full app/config import graph for a standalone script.
try:
    from dotenv import load_dotenv

    load_dotenv(SERVICE_ROOT / ".env")
except ImportError:
    pass

from api.services.visual_tutor.llm_teaching_planner import DeepSeekVisualTutorLLMClient


def main() -> int:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("DEEPSEEK_API_KEY is not set (checked env and ai-service/.env)", file=sys.stderr)
        return 1

    client = DeepSeekVisualTutorLLMClient(timeout=20)
    print(f"model: {client.model}")

    system_prompt = "You return only a single strict JSON object. No prose, no markdown fences."
    user_prompt = (
        'Return exactly this JSON object, with no other text: '
        '{"status": "ok", "note": "deepseek visual tutor smoke test"}'
    )

    try:
        raw_output = client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception as exc:  # noqa: BLE001 - want to see the real error, not swallow it
        print(f"DeepSeek request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("--- raw response ---")
    print(raw_output)
    print("--------------------")

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        print(f"Response was not valid JSON: {exc}", file=sys.stderr)
        return 1

    print("parsed JSON:", json.dumps(parsed, indent=2, ensure_ascii=False))
    print("\nSUCCESS: one real DeepSeek round trip, valid JSON back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
