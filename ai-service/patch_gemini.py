from google import genai
from google.genai import types
import os

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
        # Initializing without api_key automatically uses Application Default Credentials (CLI OAuth)
        self.client = genai.Client()

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
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
