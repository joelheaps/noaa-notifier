from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from time import sleep

import feedparser
import httpx
import structlog
import tomli

logger = structlog.get_logger()

logger.info("Loading config.", file="config.toml")
with open("config.toml", "rb") as f:
    config = tomli.load(f)

NOAA_RSS_FEED_URL: str = config["urls"]["noaa_rss_feed_url"]
DISCORD_WEBHOOK_URL: str = config["urls"]["discord_webhook_url"]
SEEN_ALERTS_CACHE = Path(config["storage"]["seen_alerts_cache"])
TITLE_MUST_NOT_INCLUDE: list[str] = config["filters"]["title_must_not_include"]
SUMMARY_MUST_NOT_INCLUDE: list[str] = config["filters"]["summary_must_not_include"]
SUMMARY_MUST_INCLUDE: list[str] = config["filters"]["summary_must_include"]

CLEAN_HTML_REGEX = re.compile("<.*?>")


def cleanup_summary(string_: str) -> str:
    cleaned = re.sub(CLEAN_HTML_REGEX, "", string_)
    cleaned = cleaned.replace("Read more", "")
    return cleaned.strip()


def notify_discord(
    entry: feedparser.FeedParserDict,
    webhook_url: str = DISCORD_WEBHOOK_URL,
) -> None:
    """Sends Discord message containing summary and link to SPC alert."""
    logger.info(
        "Notifying Discord of new NOAA alert or product.", product=entry["title"]
    )

    # Summaries contain HTML tags that Discord can't display properly.
    # Cleanup summary text
    entry["summary"] = cleanup_summary(entry["summary"])  # type: ignore

    result = httpx.post(
        webhook_url,
        json={
            "content": entry["title"],
            "embeds": [
                {
                    "title": entry["title"],
                    "url": entry["link"],
                    "description": entry["summary"],
                },
            ],
        },
    )

    result.raise_for_status()


def get_hash(entry: feedparser.FeedParserDict) -> str:
    """Generate a hash for a dictionary or string. Used for deduplicating alerts."""
    as_str = json.dumps(entry)
    return sha256(as_str.encode()).hexdigest()


def load_seen_alerts(seen_alerts_file: Path = SEEN_ALERTS_CACHE) -> set[str]:
    logger.info("Loading previously seen alerts.", path=SEEN_ALERTS_CACHE)
    try:
        with seen_alerts_file.open("r") as f:
            seen_alerts: set[str] = set(json.load(f))
        logger.info("Loaded previously seen alerts.", count=len(seen_alerts))
    except FileNotFoundError:
        logger.info("Could not load previously seen alerts; file does not exist.")
        seen_alerts = set()
    return seen_alerts


def store_seen_alerts(
    seen_alerts: set[str], seen_alerts_file: Path = SEEN_ALERTS_CACHE
) -> None:
    logger.info("Storing seen alerts.", count=len(seen_alerts))


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
            title=entry["title"]
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
            notify_discord(item)
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
    SEEN_ALERTS_CACHE.parent.mkdir(parents=True, exist_ok=True)

    if args.loop:
        while True:
            main()
            logger.info("Sleeping for 60 seconds.")
            sleep(60)
    else:
        main()
