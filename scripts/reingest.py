#!/usr/bin/env python3
"""Re-ingestion script for Render deployments.

Render's free tier uses an ephemeral filesystem, which wipes the ChromaDB
store on every deployment. This script allows you to rapidly re-ingest the
knowledge base immediately after a deploy.

Usage:
    python3 scripts/reingest.py [clone_id]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.ingest import ingest_clone_data
from app.vector_store import delete_collection

async def main() -> None:
    parser = argparse.ArgumentParser(description="Re-ingest knowledge base after deploy.")
    parser.add_argument(
        "clone_id",
        nargs="?",
        default="alucard",
        help="The clone ID to re-ingest (default: alucard)",
    )
    args = parser.parse_args()

    clone_id = args.clone_id
    print(f"Starting re-ingestion for clone: {clone_id}")

    # First delete existing collection if any
    deleted = await delete_collection(clone_id)
    if deleted:
        print(f"Cleared existing collection for {clone_id}.")
    else:
        print(f"No existing collection found for {clone_id}.")

    # Ingest all data
    try:
        stats = await ingest_clone_data(clone_id)
        print(f"Successfully re-ingested {stats.chunks_created} chunks from {stats.files_processed} files for {clone_id}.")
    except Exception as e:
        print(f"Error during ingestion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
