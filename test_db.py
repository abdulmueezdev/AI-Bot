import asyncio
import json
from app.vector_store import VectorStore

async def main():
    vs = VectorStore()
    stats = await vs.get_collection_stats('alucard')
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
