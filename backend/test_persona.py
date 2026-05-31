import asyncio
from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    client = TestClient(app)
    queries = [
        "hi",
        "how are you?",
        "what do you think about your father?",
        "What are you working on right now?",
        "That sounds bleak. Is there anything that brings you joy?"
    ]
    for q in queries:
        print(f"\n--- USER: {q}")
        res = client.post("/chat/alucard", json={"message": q, "session_id": "test_session_123"})
        if res.status_code == 200:
            print(f"--- ALUCARD: {res.json().get('response', res.text)}\n")
        else:
            print(f"--- ERROR: {res.status_code} - {res.text}\n")

if __name__ == "__main__":
    run_tests()
