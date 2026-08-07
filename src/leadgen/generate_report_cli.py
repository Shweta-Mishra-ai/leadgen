from __future__ import annotations

import logging
import sys

from leadgen.config import get_settings
from leadgen.logging_config import configure_logging
from leadgen.report import generate_report
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.cli")


def main() -> int:
    configure_logging()
    try:
        settings = get_settings()
    except Exception as e:  # noqa: BLE001
        logger.error("Configuration error: %s", e)
        return 1

    store = LeadStore(settings.db_path)
    try:
        path = generate_report(settings, store)
    except ValueError as e:
        logger.error(str(e))
        return 1
    except Exception as e:  # noqa: BLE001
        logger.error("Report generation failed: %s", e)
        return 1

    logger.info("Report written to %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
