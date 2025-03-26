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

from spc_notifier.config import NOAA_RSS_FEED_URL, SEEN_ALERTS_CACHE, WEBHOOKS
from spc_notifier.messaging import send_discord_message
from spc_notifier.models import SpcProduct

logger = structlog.get_logger()

POLL_INTERVAL_SECONDS: int = 60
_SEEN_PRODUCTS_CACHE = Path(SEEN_ALERTS_CACHE)
SPC_PRODUCT_CACHE_SIZE: int = 500

"""
TODO:
    - Move filtering to messaging (main shouldn't care about filtering on a
      per-webhook basis)
    - Add a FilterSet tuple to models
"""


def save_seen_products(
    products: deque[SpcProduct], cache_file: Path = _SEEN_PRODUCTS_CACHE
) -> None:
    """Save seen products to disk."""
    with cache_file.open("w") as f:
        json.dump(list(products), f, indent=4)
    logger.info("Stored SPC product cache to disk.", count=len(products))


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
        logger.error("Failed to load SPC product cache from disk. Creating empty cache.")
        return deque(maxlen=SPC_PRODUCT_CACHE_SIZE)


class RssFeedError(Exception):
    """Raised when an error occurs while fetching the RSS feed."""


def get_hash(item: dict | str) -> str:
    """Generate a hash for a dictionary or string. Used for deduplicating alerts."""
    as_str = json.dumps(item)
    return sha256(as_str.encode()).hexdigest()


def _check_contains_term(terms: list[str], string_: str) -> bool:
    """Check if string contains at least one of the terms provided."""
    string_ = string_.lower()
    return any(term.lower() in string_ for term in terms)


def check_passes_filters(
    product: SpcProduct,
    title_must_include: list[str],
    title_must_not_include: list[str],
    summary_must_include: list[str],
    summary_must_not_include: list[str],
) -> bool:
    """Determines whether an entry contains wanted and unwanted terms."""
    # Check title and summary contain at least one necessary term each
    title_include_ok = (
        _check_contains_term(title_must_include, product.title)
        if title_must_include
        else True
    )
    title_exclude_ok = (
        not _check_contains_term(title_must_not_include, product.title)
        if title_must_not_include
        else True
    )

    summary_include_ok = (
        _check_contains_term(summary_must_include, product.summary)
        if summary_must_include
        else True
    )
    summary_exclude_ok = (
        not _check_contains_term(summary_must_not_include, product.summary)
        if summary_must_not_include
        else True
    )

    if (
        title_include_ok
        and title_exclude_ok
        and summary_include_ok
        and summary_exclude_ok
    ):
        return True

    logger.info(
        "Product did not pass filters.",
        product=product.title,
        title_include_terms="pass" if title_include_ok else "fail",
        title_exclude_terms="pass" if title_exclude_ok else "fail",
        summary_include_terms="pass" if summary_include_ok else "fail",
        summary_exclude_terms="pass" if summary_exclude_ok else "fail",
    )
    return False


def process_feed_entries(
    feed: feedparser.FeedParserDict, seen_products: deque[str]
) -> deque[str]:
    seen_count = 0  # Just used for generating a message later

    for item in feed["entries"]:
        logger.debug("Processing product: %s", item["title"])

        product = SpcProduct(
            title=item["title"], summary=item["summary"], link=item["link"]
        )

        try:
            hash_ = get_hash(product.summary)
        except KeyError:
            logger.exception("Skipping entry with empty summary.", title=product.title)
            continue

        if hash_ in seen_products:
            seen_count += 1
            continue

        send_success = True

        for wh_config in WEBHOOKS:
            logger.debug("Processing webhook.", url=wh_config.url)
            if not check_passes_filters(
                product=product,
                title_must_include=wh_config.title_must_include,
                title_must_not_include=wh_config.title_must_not_include,
                summary_must_include=wh_config.summary_must_include,
                summary_must_not_include=wh_config.summary_must_not_include,
            ):
                continue

            try:
                send_discord_message(product, wh_config)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Error sending message for product.",
                    title=product.title,
                    error=str(e),
                )
                send_success = False

        if send_success:
            if hash_ not in seen_products:
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
