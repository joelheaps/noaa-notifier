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

from spc_notifier.config import (
    NOAA_RSS_FEED_URL,
    SEEN_ALERTS_CACHE,
    SUMMARY_MUST_INCLUDE,
    SUMMARY_MUST_NOT_INCLUDE,
    TITLE_MUST_NOT_INCLUDE,
)
from spc_notifier.messaging import send_discord_message

logger = structlog.get_logger()

POLL_INTERVAL_SECONDS: int = 60
_SEEN_ALERTS_CACHE = Path(SEEN_ALERTS_CACHE)
SEEN_ALERTS_CACHE_SIZE: int = 500


class RssFeedError(Exception):
    """Raised when an error occurs while fetching the RSS feed."""


def get_hash(item: dict | str) -> str:
    """Generate a hash for a dictionary or string. Used for deduplicating alerts."""
    as_str = json.dumps(item)
    return sha256(as_str.encode()).hexdigest()


def load_seen_alerts(seen_alerts_file: Path = _SEEN_ALERTS_CACHE) -> set[str]:
    logger.info("Loading previously seen alerts.", path=seen_alerts_file)
    try:
        with seen_alerts_file.open("r") as f:
            seen_alerts: deque[str] = deque(json.load(f), maxlen=SEEN_ALERTS_CACHE_SIZE)
        logger.info("Loaded previously seen alerts.", count=len(seen_alerts))
    except FileNotFoundError:
        logger.info("Could not load previously seen alerts; file does not exist.")
        seen_alerts: deque[str] = deque(maxlen=SEEN_ALERTS_CACHE_SIZE)
    return seen_alerts


def store_seen_alerts(
    seen_alerts: deque[str], seen_alerts_file: Path = _SEEN_ALERTS_CACHE
) -> None:
    logger.info("Storing seen alerts.", count=len(seen_alerts), path=seen_alerts_file)

    with seen_alerts_file.open("w") as f:
        json.dump(list(seen_alerts), f, indent=4)


def _check_contains_term(terms: list[str], string_: str) -> bool:
    """Check if string contains at least one of the terms provided."""
    string_ = string_.lower()
    return any(term.lower() in string_ for term in terms)


def check_passes_term_filters(title: str, summary: str) -> bool:
    """Determines whether an entry contains wanted and unwanted terms."""
    # Check summary contains at least one necessary term
    if not _check_contains_term(SUMMARY_MUST_INCLUDE, summary):  # type: ignore
        logger.info(
            "Skipping product; summary did not include at least one necessary term.",
            terms=SUMMARY_MUST_INCLUDE,
            title=title,
        )
        return False

    # Check title and summary for unwanted terms
    if _check_contains_term(TITLE_MUST_NOT_INCLUDE, title) or _check_contains_term(
        SUMMARY_MUST_NOT_INCLUDE, summary
    ):  # type: ignore
        logger.info(
            "Skipping product; title or summary contained unwanted term.",
            title=title,
        )
        return False
    return True


def process_feed_entries(
    feed: feedparser.FeedParserDict, seen_alerts: deque[str]
) -> deque[str]:
    seen_count = 0  # Just used for generating a message later

    for item in feed["entries"]:
        title = item["title"]
        summary = item["summary"]
        link = item["link"]

        try:
            hash_ = get_hash(summary)
        except KeyError:
            logger.exception("Skipping entry with empty summary.", title=title)
            continue

        if hash_ in seen_alerts:
            seen_count += 1
            seen_alerts.append(hash_)
            continue

        if not check_passes_term_filters(title, summary):
            seen_alerts.append(hash_)
            continue

        try:
            send_discord_message(title, summary, link)
            seen_alerts.append(hash_)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Error sending message for product.", title=title, error=str(e)
            )

    logger.info("Skipped previously seen products.", count=seen_count)
    return seen_alerts


@retry(on=RssFeedError, attempts=3)
def main(loop: bool) -> None:  # noqa: FBT001
    """Main execution function."""
    logger.info("Ensuring storage path for seen alerts cache exists.")
    _SEEN_ALERTS_CACHE.parent.mkdir(parents=True, exist_ok=True)

    seen_alerts: deque[str] = load_seen_alerts()

    while True:
        feed = feedparser.parse(NOAA_RSS_FEED_URL)
        if len(feed["entries"]) == 0:
            logger.error("No entries found in feed")
            raise RssFeedError

        logger.info(
            "Retrieved SPC product entries from NOAA RSS feed.",
            count=len(feed["entries"]),
        )

        seen_alerts = process_feed_entries(feed, seen_alerts)
        store_seen_alerts(seen_alerts)

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
