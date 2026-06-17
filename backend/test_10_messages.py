import requests
import json
import time

url = "http://localhost:8000/chat/alucard"
session_id = "long-test-001"
messages = [
    "I have been feeling really overwhelmed lately with everything I need to do.",
    "It is mostly my studies. I feel like I am falling behind no matter how hard I try.",
    "Did you ever feel that way about your own work?",
    "How did you deal with it?",
    "I think I am also just tired of disappointing people.",
    "Sometimes I wonder if I am even good at anything.",
    "Thank you for listening, by the way.",
    "What do you do when you cannot write anything good?",
    "Does your father know you feel this way?",
    "I should probably go. Talking to you actually helped a bit."
]

for i, msg in enumerate(messages):
    print(f"\n--- MESSAGE {i+1} ---")
    print(f"User: {msg}")
    try:
        response = requests.post(url, json={"message": msg, "session_id": session_id})
        data = response.json()
        print(f"Kafka: {data.get('response')}")
        # Add a tiny delay to ensure proper sequencing if needed
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
