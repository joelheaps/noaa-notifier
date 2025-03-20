from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from time import sleep

import feedparser
import structlog

from spc_notifier.alerting.discord import send_discord_alert
from spc_notifier.config import (
    NOAA_RSS_FEED_URL,
    SUMMARY_MUST_INCLUDE,
    SUMMARY_MUST_NOT_INCLUDE,
    TITLE_MUST_NOT_INCLUDE,
)

logger = structlog.get_logger()

_SEEN_ALERTS_CACHE = Path("./seen_alerts.json")


def get_hash(entry: feedparser.FeedParserDict) -> str:
    """Generate a hash for a dictionary or string. Used for deduplicating alerts."""
    as_str = json.dumps(entry)
    return sha256(as_str.encode()).hexdigest()


def load_seen_alerts(seen_alerts_file: Path = _SEEN_ALERTS_CACHE) -> set[str]:
    logger.info("Loading previously seen alerts.", path=seen_alerts_file)
    try:
        with seen_alerts_file.open("r") as f:
            seen_alerts: set[str] = set(json.load(f))
        logger.info("Loaded previously seen alerts.", count=len(seen_alerts))
    except FileNotFoundError:
        logger.info("Could not load previously seen alerts; file does not exist.")
        seen_alerts = set()
    return seen_alerts


def store_seen_alerts(
    seen_alerts: set[str], seen_alerts_file: Path = _SEEN_ALERTS_CACHE
) -> None:
    logger.info("Storing seen alerts.", count=len(seen_alerts), path=seen_alerts_file)

    with seen_alerts_file.open("w") as f:
        seen_alerts_as_list = list(seen_alerts)
        json.dump(seen_alerts_as_list, f, indent=4)


def _check_contains_term(terms: list[str], string_: str) -> bool:
    """Check if string contains at least one of the terms provided."""
    string_ = string_.lower()
    return any(term.lower() in string_ for term in terms)


def check_passes_term_filters(entry: feedparser.FeedParserDict) -> str | None:
    """Determines whether an entry contains wanted and unwanted terms."""
    # Check summary contains at least one necessary term
    if not _check_contains_term(SUMMARY_MUST_INCLUDE, entry["summary"]):  # type: ignore
        logger.info(
            "Skipping product; summary did not include at least one necessary term.",
            terms=SUMMARY_MUST_INCLUDE,
            title=entry["title"],
        )
        return False

    # Check title and summary for unwanted terms
    if _check_contains_term(
        TITLE_MUST_NOT_INCLUDE, entry["title"]
    ) or _check_contains_term(SUMMARY_MUST_NOT_INCLUDE, entry["summary"]):  # type: ignore
        logger.info(
            "Skipping product; title or summary contained unwanted term.",
            title=entry["title"],
        )
        return False
    return True


def main() -> None:
    seen_alerts: set[str] = load_seen_alerts()
    feed = feedparser.parse(NOAA_RSS_FEED_URL)

    for item in feed["entries"]:
        try:
            hash_ = get_hash(item["summary"])
        except KeyError:
            logger.exception("Skipping entry with empty summary.", title=item["title"])
            continue

        # Skip seen alerts
        if hash_ in seen_alerts:
            logger.info("Skipping previously seen product.", title=item["title"])
            seen_alerts.add(hash_)
            continue

        if not check_passes_term_filters(item):
            seen_alerts.add(hash_)
            continue

        # Send notification
        try:
            send_discord_alert(item)
            seen_alerts.add(hash_)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Error sending message for product.", title=item["title"], error=str(e)
            )

    store_seen_alerts(seen_alerts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop")
    args = parser.parse_args()

    logger.info("Ensuring storage path for seen alerts cache exists.")
    _SEEN_ALERTS_CACHE.parent.mkdir(parents=True, exist_ok=True)

    if args.loop:
        while True:
            main()
            logger.info("Sleeping for 60 seconds.")
            sleep(60)
    else:
        main()
