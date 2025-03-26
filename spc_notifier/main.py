from __future__ import annotations

import argparse
import json
from collections import deque
from hashlib import sha256
from pathlib import Path
from time import sleep

import feedparser
import structlog
from stamina import retry

from spc_notifier.config import NOAA_RSS_FEED_URL, SEEN_ALERTS_CACHE
from spc_notifier.messaging import submit_for_notification
from spc_notifier.models import SpcProduct

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(LOG_MODE))
logger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS: int = 60
_SEEN_PRODUCTS_CACHE = Path(SEEN_ALERTS_CACHE)
SPC_PRODUCT_CACHE_SIZE: int = 500


class RssFeedError(Exception):
    """Raised when an error occurs while fetching the RSS feed."""


def save_seen_products(
    products: deque[SpcProduct], cache_file: Path = _SEEN_PRODUCTS_CACHE
) -> None:
    """Save seen products to disk."""
    with cache_file.open("w") as f:
        json.dump(list(products), f, indent=4)


def load_seen_products(cache_file: Path = _SEEN_PRODUCTS_CACHE) -> deque[SpcProduct]:
    """Load seen products from disk."""
    try:
        with cache_file.open("r") as f:
            products = json.load(f)
        logger.info("Loaded SPC product cache from disk.", count=len(products))
        return deque(products, maxlen=SPC_PRODUCT_CACHE_SIZE)
    except FileNotFoundError:
        return deque(maxlen=SPC_PRODUCT_CACHE_SIZE)
    except json.JSONDecodeError:
        logger.exception("Failed to load cache from disk. Creating empty cache.")
        return deque(maxlen=SPC_PRODUCT_CACHE_SIZE)


def get_hash(item: dict | str) -> str:
    """Generate a hash for a dictionary or string. Used for deduplicating alerts."""
    as_str = json.dumps(item)
    return sha256(as_str.encode()).hexdigest()


def process_feed_entries(
    feed: feedparser.FeedParserDict, seen_products: deque[str]
) -> deque[str]:
    seen_count = 0  # Just used for generating a message later

    for item in feed["entries"]:
        logger.debug("Processing product.", title=item["title"])

        product = SpcProduct(
            title=item["title"], summary=item["summary"], link=item["link"]
        )

        try:
            hash_ = get_hash(product.summary)
        except KeyError:
            logger.exception("Skipping entry with empty summary.", title=product.title)
            continue

        if hash_ in seen_products:
            logger.debug("Product previously seen product.", title=product.title)
            seen_count += 1
            continue

        try:
            submit_for_notification(product)
            send_success = True
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Error sending message for product. Will retry during next loop.",
                title=product.title,
                error=str(e),
            )
            send_success = False

        # If notification failed for product, don't mark as seen to allow retry in future
        if send_success and hash_ not in seen_products:
            seen_products.append(hash_)

    logger.info("Skipped previously seen products.", count=seen_count)
    return seen_products


@retry(on=RssFeedError, attempts=3)
def main(loop: bool) -> None:  # noqa: FBT001
    """Main execution function."""
    logger.info("Ensuring storage path for seen products cache exists.")
    _SEEN_PRODUCTS_CACHE.parent.mkdir(parents=True, exist_ok=True)

    seen_products: deque[str] = load_seen_products()

    while True:
        feed = feedparser.parse(NOAA_RSS_FEED_URL)
        if len(feed["entries"]) == 0:
            logger.error("No entries found in feed")
            raise RssFeedError

        logger.info(
            "Retrieved SPC product entries from NOAA RSS feed.",
            count=len(feed["entries"]),
        )

        seen_products = process_feed_entries(feed, seen_products)
        save_seen_products(seen_products)

        if not loop:
            break

        logger.info("Sleeping for 60 seconds. Press Ctrl+C to exit.")
        sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop")
    args = parser.parse_args()

    try:
        main(loop=args.loop)
    except KeyboardInterrupt:
        logger.info("Exiting application.")
