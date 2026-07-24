import asyncio
import httpx

async def test_prod_bio():
    url = "https://ai-bot-tp8d.onrender.com/chat/alucard"
    session_id = "biography-test-prod-001"
    
    questions = [
        "what is your brothers name",
        "do you have siblings",
        "tell me about your mother",
        "what year is it and what is happening in the world",
        "who is your closest friend",
        "what was your grandfathers profession"
    ]
    
    print("Waiting 120 seconds for Render to deploy the new commit...")
    await asyncio.sleep(120)
    
    print("--- Starting Production Biography Test ---")
    async with httpx.AsyncClient(timeout=120.0) as client:
        for q in questions:
            print(f"\nUser: {q}")
            try:
                response = await client.post(
                    url, 
                    json={"message": q, "session_id": session_id}
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"Kafka: {data.get('response', '')}")
                else:
                    print(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Request Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_prod_bio())
