from __future__ import annotations

import logging
import sys

from leadgen.config import get_settings
from leadgen.logging_config import configure_logging
from leadgen.pipeline import run_pipeline
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.cli")


def main() -> int:
    configure_logging()
    try:
        settings = get_settings()
    except Exception as e:  # noqa: BLE001 - config errors must produce a clear exit, not a traceback
        logger.error("Configuration error: %s", e)
        return 1

    logger.info("active sources: %s", settings.active_source_names())
    store = LeadStore(settings.db_path)

    try:
        summary = run_pipeline(settings, store)
    except Exception as e:  # noqa: BLE001
        logger.error("Pipeline run failed: %s", e)
        return 1

    store.export_csv("leads.csv")
    logger.info("Total leads in store: %d", store.count())
    logger.info("Summary: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
