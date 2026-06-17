import asyncio
from app.orchestrator import handle_chat

async def main():
    result = await handle_chat("alucard", "session_123", "tell me about your father")
    print(f"Response: {result.response[:50]}...")
    print(f"Context chunks used: {result.debug_info.context_chunks_used}")

asyncio.run(main())
