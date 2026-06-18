import asyncio
import httpx

async def test_local_bio():
    url = "http://localhost:8000/chat/alucard"
    session_id = "biography-test-001"
    
    questions = [
        "what is your brothers name",
        "do you have siblings",
        "tell me about your mother",
        "what year is it and what is happening in the world",
        "who is your closest friend",
        "what was your grandfathers profession"
    ]
    
    print("--- Starting Local Biography Test ---")
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
    asyncio.run(test_local_bio())
