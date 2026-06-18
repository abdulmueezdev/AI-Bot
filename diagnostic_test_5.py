import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.embedder import embed_query
from app.vector_store import query as vector_query

async def test():
    queries = [
        'what is your hobby', 
        'do you have a loved one', 
        'tell me about your office job',
        'free time',
        'explain your life'
    ]
    for q in queries:
        emb = await embed_query(q, clone_id='alucard')
        results = await vector_query('alucard', emb, top_k=5)
        print(f'\n--- Query: {q} ---')
        for r in results:
            text = getattr(r, 'text', '')[:80].replace(chr(10), ' ')
            print(f'  score={getattr(r, "similarity", "?")} | {text}...')

if __name__ == "__main__":
    asyncio.run(test())
