import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.orchestrator import handle_chat
from app.memory_manager import reset_session

async def test_chat():
    session_id = "fix_a_verification_session_v2"
    
    # Just in case, try to reset the session if the function exists
    try:
        await reset_session('alucard', session_id)
    except Exception:
        pass
        
    messages = [
        "Hi, Kafka. How are you feeling today?",
        "What are your hobbies? What do you do in your free time?",
        "Do you have a loved one? Someone special?",
        "Tell me about your office job. What do you do there?",
        "Can you explain your life to me in a few sentences?",
        "How is your relationship with your father?",
        "What are you currently writing?",
        "If you could travel anywhere, where would you go?"
    ]
    
    print("--- Starting Conversation Test ---")
    for msg in messages:
        print(f"\nUser: {msg}")
        # Call the orchestrator
        response = await handle_chat(
            clone_id='alucard', 
            session_id=session_id, 
            message=msg
        )
        print(f"Kafka: {response}")

if __name__ == "__main__":
    asyncio.run(test_chat())
