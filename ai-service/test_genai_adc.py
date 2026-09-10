from google import genai
import google.auth
import os

try:
    credentials, project_id = google.auth.default()
    project = os.getenv("GOOGLE_CLOUD_PROJECT", project_id) or getattr(credentials, "quota_project_id", None)
    print(f"Resolved project: {project}")
    if project:
        # vertexai=True uses Google Cloud
        client = genai.Client(vertexai=True, project=project, location="us-central1")
        print("Sending prompt...")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Say 'Hello from Gemini ADC!'"
        )
        print("Response:", response.text)
    else:
        print("No project found.")
except Exception as e:
    import traceback
    traceback.print_exc()
