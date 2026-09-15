import requests
import time
import json
import sys

print("Waiting 5s for server to start...")
time.sleep(5)

queries = [
    "What would Marcus Aurelius say about Kafka's guilt?",
    "Compare Nietzsche and Stoicism on suffering.",
    "My name is Abdul Mueez and I like Camus.",
    "What is my name and what philosopher do I like?",
    "How does Kafka view the absurdity of existence?",
    "What did Socrates say about death?",
    "Can you quote Marcus Aurelius on patience?",
    "Is the Gregor Samsa transformation a punishment?",
    "What is the difference between Stoic and Existentialist views on fate?",
    "Tell me about the dialectic between Plato and Aristotle."
]

session_id = "abdul_mueez_session"
results = []

for i, q in enumerate(queries, 1):
    print(f"\n--- Test {i} ---")
    print(f"Query: {q}")
    payload = {"message": q, "session_id": session_id}
    
    try:
        start = time.time()
        resp = requests.post("http://localhost:8000/chat/alucard", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"Response JSON: {json.dumps(data, indent=2)}")
        results.append(data)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

print("\nALL_DONE")
