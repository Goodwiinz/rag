#!/usr/bin/env python3
"""
Script to run bulk ingestion of 500k ArXiv papers.
Run inside the container: python scripts/run_bulk_ingestion.py
"""

import asyncio
import logging
import sys
import os

# Create log directory
os.makedirs("/app/data", exist_ok=True)

# Setup logging
log_file = "/app/data/bulk_ingestion.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("bulk_ingestion")


async def run_full_ingestion():
    from src.services.kaggle_bulk_ingestion import KaggleBulkIngestionService

    logger.info("=" * 60)
    logger.info("STARTING FULL 500K PAPER INGESTION")
    logger.info("=" * 60)

    # Use larger batch size for better throughput
    service = KaggleBulkIngestionService(batch_size=1000, max_papers=500000)

    def progress_cb(progress):
        batch = progress["current_batch"]
        if batch % 50 == 0:  # Log every 50 batches (50,000 papers)
            processed = progress["processed"]
            total = progress["total_papers"]
            pct = progress["progress_percent"]
            pps = progress["papers_per_second"]
            eta = progress["eta_seconds"] / 60
            logger.info(
                f"Progress: {processed:,}/{total:,} ({pct:.1f}%) - "
                f"{pps:.1f} pps - ETA: {eta:.1f} min"
            )

    try:
        result = await service.run_ingestion(
            categories=None,  # All categories
            resume=True,      # Resume from previous state
            progress_callback=progress_cb
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("INGESTION COMPLETED")
        logger.info("=" * 60)
        for k, v in result.items():
            logger.info(f"  {k}: {v}")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(run_full_ingestion())
