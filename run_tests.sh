echo "TEST 1 — hi"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "hi", "session_id": "verify-001"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 2 — how are you?"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "how are you?", "session_id": "verify-001"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 3 — father"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "tell me about your relationship with your father", "session_id": "verify-001"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 4 — writing"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "what are you working on right now?", "session_id": "verify-001"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 5 — multi-turn (1)"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "hi", "session_id": "verify-002"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 5 — multi-turn (2)"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "how is the writing going?", "session_id": "verify-002"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 5 — multi-turn (3)"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "do you ever think about leaving Prague?", "session_id": "verify-002"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 6 — anxiety"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "I have been feeling really anxious lately", "session_id": "verify-003"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"

echo -e "\nTEST 7 — meaning"
curl -s -X POST http://localhost:8000/chat/alucard -H "Content-Type: application/json" -d '{"message": "what is the meaning of life?", "session_id": "verify-003"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'Error'))"
