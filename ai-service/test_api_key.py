from api.services.visual_tutor.llm_teaching_planner import GeminiVisualTutorLLMClient
import asyncio
import os

async def run_test():
    try:
        print("Initializing Gemini Client (it should detect the API key in .env)...")
        # Ensure it loads from the newly appended .env
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        client = GeminiVisualTutorLLMClient(temperature=0.7)
        print(f"Client initialized successfully with model: {client.model}")
        
        print("\nSending prompt to Gemini Developer API...")
        response = client.complete(
            system_prompt="You are a helpful AI.",
            user_prompt="Reply exactly with 'The free tier API key is working!'"
        )
        print("\n=== GEMINI RESPONSE ===")
        print(response)
        print("=======================")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
