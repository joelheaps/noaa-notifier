from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import structlog

from spc_notifier.config import CACHE_FILE
from spc_notifier.models import SpcProduct

logger = structlog.get_logger(__name__)

_CACHE_FILE = Path(CACHE_FILE)
SPC_PRODUCT_CACHE_SIZE: int = 500


def save_seen_products(
    products: deque[SpcProduct], cache_file: Path = _CACHE_FILE
) -> None:
    """Save seen products to disk."""
    logger.info(
        "Storing seen products cache file.", count=len(products), cache_file=cache_file
    )
    with cache_file.open("w") as f:
        json.dump(list(products), f, indent=4)


def load_seen_products(cache_file: Path = _CACHE_FILE) -> deque[SpcProduct]:
    """Load seen products from disk."""
    try:
        with cache_file.open("r") as f:
            products = json.load(f)
        logger.info(
            "Loaded seen products cache from disk.",
            count=len(products),
            cache_file=cache_file,
        )
        return deque(products, maxlen=SPC_PRODUCT_CACHE_SIZE)
    except FileNotFoundError:
        logger.warning(
            "Could not find seen products cache file.  Creating empty cache.",
            file=cache_file,
        )
        return deque(maxlen=SPC_PRODUCT_CACHE_SIZE)
    except json.JSONDecodeError:
        logger.exception(
            "Failed to load cache from disk. Creating empty cache.", file=cache_file
        )
        return deque(maxlen=SPC_PRODUCT_CACHE_SIZE)
