import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.vector_store import delete_file_chunks, get_collection_count
from app.ingest import ingest_clone_data
from app.embedder import embed_query
from app.vector_store import query as vector_query

async def main():
    print("Deleting contaminated chunks...")
    deleted_meta = await delete_file_chunks('alucard', 'The_Metamorphosis.txt')
    deleted_trial = await delete_file_chunks('alucard', 'The_trail.txt')
    print(f"Deleted {deleted_meta} chunks for The_Metamorphosis.txt")
    print(f"Deleted {deleted_trial} chunks for The_trail.txt")

    print("\nRe-ingesting cleaned files...")
    meta_stats = await ingest_clone_data('alucard', file_name='The_Metamorphosis.txt')
    trial_stats = await ingest_clone_data('alucard', file_name='The_trail.txt')
    print(f"Ingested The_Metamorphosis.txt: {meta_stats.chunks_created} chunks")
    print(f"Ingested The_trail.txt: {trial_stats.chunks_created} chunks")

    print("\nChecking total collection count...")
    count = await get_collection_count('alucard')
    print(f"Total chunks in Supabase: {count}")

    print("\nRunning diagnostic queries...")
    queries = ['what is your hobby', 'do you have a loved one', 'tell me about your office job']
    for q in queries:
        emb = await embed_query(q, clone_id='alucard')
        results = await vector_query('alucard', emb, top_k=5)
        print(f'\n--- Query: {q} ---')
        for r in results:
            print(f'  score={getattr(r, "similarity", "?")} | {getattr(r, "text", "")[:80].replace(chr(10), " ")}...')

if __name__ == "__main__":
    asyncio.run(main())
