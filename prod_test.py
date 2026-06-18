import asyncio
import time
import httpx
import uuid

async def test_prod():
    print("Waiting 120 seconds for Render to deploy the new commit...")
    await asyncio.sleep(120)
    
    url = "https://ai-bot-tp8d.onrender.com/chat/alucard"
    session_id = uuid.uuid4().hex[:12]
    
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
    
    print("--- Starting Production Conversation Test ---")
    async with httpx.AsyncClient(timeout=120.0) as client:
        for msg in messages:
            print(f"\nUser: {msg}")
            try:
                response = await client.post(
                    url, 
                    json={"message": msg, "session_id": session_id}
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"Kafka: {data.get('response', '')}")
                    print(f"  [Debug: chunks={data.get('context_chunks_used')} latency={data.get('latency_ms')}]")
                else:
                    print(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Request Failed: {e}")
                
            # small sleep between requests to be gentle to the prod server
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(test_prod())
