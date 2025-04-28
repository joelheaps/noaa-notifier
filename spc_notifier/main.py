from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from time import sleep

import feedparser
import structlog
from httpx import HTTPError
from stamina import retry

from spc_notifier.cache import load_seen_products, save_seen_products
from spc_notifier.config import CACHE_FILE, LOG_MODE, NOAA_RSS_FEED_URL
from spc_notifier.filtering import check_contains_terms
from spc_notifier.messaging import submit_for_notification
from spc_notifier.models import SpcProduct

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(LOG_MODE))
logger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS: int = 60
_CACHE_FILE = Path(CACHE_FILE)
SPC_PRODUCT_CACHE_SIZE: int = 500
NO_DATA_TERMS: list[str] = ["No watches are valid", "No MDs are in effect"]


class RssFeedError(Exception):
    """Raised when an error occurs while fetching the RSS feed."""


def process_feed_entries(
    feed: feedparser.FeedParserDict, seen_products: deque[SpcProduct]
) -> deque[str]:
    seen_count = 0  # Just used for generating a message later

    for item in feed["entries"]:
        # Some entries in the RSS feed are just a filler for 'nothing to report right now'.
        if check_contains_terms(NO_DATA_TERMS, item["title"]):
            continue

        logger.debug("Processing product.", title=item["title"], item=item)

        product = SpcProduct(
            title=item["title"], summary=item["summary"], link=item["link"]
        )

        # Used for deduplication
        if not product["title"]:
            logger.exception(
                "Skipping entry with empty summary.", title=product["title"]
            )
            continue

        if product in seen_products:
            logger.debug("Product previously seen product.", title=product["title"])
            seen_count += 1
            continue

        try:
            submit_for_notification(product)
            send_success = True
        except HTTPError as e:
            logger.warning(
                "Error sending message for product. Will retry during next loop.",
                title=product["title"],
                error=str(e),
            )
            send_success = False

        # Allow failed notifications to retry in future.
        if send_success and product not in seen_products:
            seen_products.append(product)

    logger.info("Skipped previously seen products.", count=seen_count)
    return seen_products


@retry(on=RssFeedError, attempts=3)
def main(loop: bool) -> None:
    """Main execution function."""
    logger.info("Ensuring storage path for seen products cache exists.")
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    seen_products: deque[str] = load_seen_products()

    while True:
        feed = feedparser.parse(NOAA_RSS_FEED_URL)
        if len(feed["entries"]) == 0:
            logger.error("No entries found in feed")
            raise RssFeedError

        logger.info(
            "Retrieved current SPC product entries from NOAA RSS feed.",
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
