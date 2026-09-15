"""Orchestrator script for the ingestion pipeline."""

import argparse
import asyncio
import sys

import structlog

from app.prep_corpus import prep_corpus
from app.corpus_budget import estimate_corpus_budget
from app.ingest import ingest_clone_data, DailyLimitReached

logger = structlog.get_logger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Run the philosophy corpus ingestion pipeline.")
    parser.add_argument("--clone-id", type=str, default="alucard", help="Clone ID to ingest data for")
    parser.add_argument("--model", type=str, default="gemini-embedding-001", help="Embedding model to use")
    parser.add_argument("--file", type=str, default=None, help="Specific test file to ingest")
    parser.add_argument("--resume", action="store_true", help="Resume ingestion from state")
    
    args = parser.parse_args()
    
    logger.info("ingestion_pipeline_started", clone_id=args.clone_id)
    logger.info("monitoring", message="If 1,000 RPD limit exists, we will hit it at chunk ~1,000. Monitoring...")
    
    # 1. Prep Corpus
    try:
        logger.info("running_prep_corpus", clone_id=args.clone_id)
        prep_corpus(clone_id=args.clone_id)
    except Exception as e:
        logger.error("prep_corpus_failed", clone_id=args.clone_id, error=str(e))
        sys.exit(1)
        
    # 2. Estimate Budget
    try:
        logger.info("running_corpus_budget", clone_id=args.clone_id)
        estimate_corpus_budget(clone_id=args.clone_id)
    except Exception as e:
        logger.error("corpus_budget_failed", clone_id=args.clone_id, error=str(e))
        sys.exit(1)
        
    # 3. Ingest Data
    try:
        logger.info("running_ingest_data", clone_id=args.clone_id)
        # Passed limit for testing/mocking
        stats = await ingest_clone_data(
            clone_id=args.clone_id,
            file_name=args.file
        )
        logger.info("ingestion_pipeline_completed", clone_id=args.clone_id, stats=str(stats))
    except DailyLimitReached:
        print("\n⏸️ INGESTION PAUSED — Daily Gemini limit reached. Run again tomorrow to auto-resume.\n")
        logger.info("ingestion_paused_daily_limit", clone_id=args.clone_id)
    except Exception as e:
        logger.error("ingestion_failed", clone_id=args.clone_id, error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
