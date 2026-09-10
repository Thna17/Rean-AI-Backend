import asyncio
import os
from api.services.visual_tutor.llm_teaching_planner import GeminiVisualTutorLLMClient

async def test_gemini():
    print("Initializing Gemini Client...")
    try:
        client = GeminiVisualTutorLLMClient(temperature=0.7)
        print(f"Client initialized with model: {client.model}")
        
        print("\nSending test prompt to Gemini...")
        response = client.complete(
            system_prompt="You are a helpful AI.",
            user_prompt="Say 'Authentication successful!'"
        )
        print("\n=== GEMINI RESPONSE ===")
        print(response)
        print("=======================")
        
    except Exception as e:
        print("\n=== ERROR ===")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini())
