import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure system-wide structured logger."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # HTTP client and model-download libraries log every request/byte at DEBUG: keep the app log readable.
    for noisy in ("httpx", "httpcore", "urllib3", "huggingface_hub", "filelock", "PIL", "asyncio", "pymongo", "qdrant_client",
                  "python_multipart", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logger = logging.getLogger("datn_finance")
    return logger


logger = setup_logging()
