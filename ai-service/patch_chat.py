import re

path = "/Users/macbookpro/Desktop/Development/AI Project/ReanAI/ai-service/api/routes/ai_tutor_chat.py"
with open(path, "r") as f:
    content = f.read()

# Replace the previous block with the fixed Vertex AI one
old_block = """                    provider = os.getenv("VISUAL_TUTOR_LLM_PROVIDER", "auto").strip().lower()
                    if provider == "gemini":
                        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
                        model_used = f"gemini/{gemini_model}"
                        from google import genai
                        from google.genai import types
                        genai_client = genai.Client()"""

new_block = """                    provider = os.getenv("VISUAL_TUTOR_LLM_PROVIDER", "auto").strip().lower()
                    if provider == "gemini":
                        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
                        model_used = f"gemini/{gemini_model}"
                        from google import genai
                        from google.genai import types
                        import google.auth
                        
                        api_key = os.getenv("GEMINI_API_KEY")
                        if api_key:
                            genai_client = genai.Client(api_key=api_key)
                        else:
                            credentials, project_id = google.auth.default()
                            project = os.getenv("GOOGLE_CLOUD_PROJECT", project_id)
                            if not project:
                                raise ValueError("No Google Cloud Project found for ADC. Set GOOGLE_CLOUD_PROJECT.")
                            genai_client = genai.Client(vertexai=True, project=project, location="us-central1")"""

content = content.replace(old_block, new_block)

with open(path, "w") as f:
    f.write(content)
