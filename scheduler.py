"""
Scheduler - runs the pipeline on a set interval.
Always runs once immediately on startup, then every N hours after that.
Set SCHEDULE_INTERVAL_HOURS env var (default: 10).
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

INTERVAL_HOURS   = float(os.getenv("SCHEDULE_INTERVAL_HOURS", "10"))
INTERVAL_SECONDS = INTERVAL_HOURS * 3600


def run_pipeline_safe():
    try:
        from main import run_pipeline
        log.info(f"Pipeline starting at {datetime.now(timezone.utc).isoformat()}")
        run_pipeline()
        log.info("Pipeline complete")
    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)


def run_once():
    from main import run_pipeline
    log.info(f"Running pipeline at {datetime.now(timezone.utc).isoformat()}")
    success = run_pipeline()
    if not success:
        log.error("Pipeline failed — check logs")
        sys.exit(1)
    log.info("Pipeline complete")


def run_loop():
    log.info(f"Scheduler started — runs every {INTERVAL_HOURS}h")

    # Run immediately on startup so Railway deploys always produce a video
    log.info("Running immediately on startup...")
    run_pipeline_safe()

    # Then run every N hours
    while True:
        next_run = INTERVAL_SECONDS
        log.info(f"Next run in {INTERVAL_HOURS}h — sleeping...")
        time.sleep(next_run)
        run_pipeline_safe()


if __name__ == "__main__":
    if "--once" in sys.argv or os.getenv("RUN_MODE") == "once":
        run_once()
    else:
        run_loop()
