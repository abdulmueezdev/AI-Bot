import requests
import json
import time
import uuid

base_url = "https://ai-bot-tp8d.onrender.com"
clone_id = "alucard"
session_id = f"e2e_test_{uuid.uuid4().hex[:8]}"

headers = {"Content-Type": "application/json"}

queries = [
    "Who are you?",
    "What is your view on hope?",
    "What's on your calendar today?",
    "Based on what you just said about hope, how does that relate to your daily life?",
]

print(f"Starting E2E Session Test | Session ID: {session_id}")

for i, q in enumerate(queries, 1):
    print(f"\n--- Request {i} ---")
    print(f"User: {q}")
    payload = {"message": q, "session_id": session_id}
    
    start_time = time.time()
    try:
        response = requests.post(f"{base_url}/chat/{clone_id}", json=payload, headers=headers)
        duration = time.time() - start_time
        if response.status_code == 200:
            print(f"Bot ({duration:.2f}s): {response.json().get('response', '')}")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        
print(f"\n--- Ending Session ---")
response = requests.post(f"{base_url}/session/end/{clone_id}/{session_id}")
if response.status_code == 200:
    print(f"Session ended successfully. Status: {response.status_code}")
else:
    print(f"Failed to end session. Status: {response.status_code} | Response: {response.text}")

