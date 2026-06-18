__test__ = False

import asyncio
import sys
# Set up paths so we can import app modules properly
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.embedder import embed_query
from app.vector_store import query as vector_query

async def test():
    queries = ['what is your hobby', 'do you have a loved one', 'tell me about your office job']
    for q in queries:
        emb = await embed_query(q, clone_id='alucard')
        results = await vector_query('alucard', emb, top_k=5)
        print(f'\n--- Query: {q} ---')
        for r in results:
            # handle potential missing fields safely
            print(f'  score={getattr(r, "similarity", "?")} | {getattr(r, "text", "")[:80].replace(chr(10), " ")}...')

if __name__ == "__main__":
    asyncio.run(test())
