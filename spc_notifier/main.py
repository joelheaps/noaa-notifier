import json
import re
from hashlib import sha256
from pathlib import Path
from time import sleep
from typing import Any

import feedparser
import httpx
import structlog

logger = structlog.get_logger()

NOAA_RSS_FEED_URL: str = "https://www.spc.noaa.gov/products/spcrss.xml"
DISCORD_WEBHOOK_URL: str = ""

SEEN_ALERTS_CACHE = Path("./seen_alerts.json")
SKIP_TITLE_TERMS: list[str] = ["No watches are valid", "Fire"]
SKIP_SUMMARY_TERMS: list[str] = ["HAS NOT BEEN ISSUED YET"]
SUMMARY_MUST_INCLUDE: list[str] = ["Nebraska", "Iowa"]

CLEAN_HTML_REGEX = re.compile("<.*?>")


def cleanup_summary(string_: str) -> str:
    cleaned = re.sub(CLEAN_HTML_REGEX, "", string_)
    cleaned = cleaned.replace("Read more", "")
    return cleaned.strip()


def notify_discord(
    entry: dict[Any, Any],
    webhook_url: str = DISCORD_WEBHOOK_URL,
) -> None:
    """Sends Discord message containing summary and link to SPC alert."""
    logger.info(
        "Notifying Discord of new NOAA alert or product.", product=entry["title"]
    )
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
    try:
        result.raise_for_status()
    except Exception:
        logger.exception()


def check_skip(
    entry: feedparser.FeedParserDict,
    skip_title_terms: list[str] = SKIP_TITLE_TERMS,
    skip_summary_terms: list[str] = SKIP_SUMMARY_TERMS,
) -> bool:
    return check_contains_term(skip_title_terms, entry["title"]) or check_contains_term(  # type: ignore
        skip_summary_terms,
        entry["summary"],  # type: ignore
    )


def check_contains_term(terms: list[str], string_: str) -> bool:
    string_ = string_.lower()
    return any(term.lower() in string_ for term in terms)


def get_hash(entry: feedparser.FeedParserDict) -> str:
    as_str = json.dumps(entry)
    return sha256(as_str.encode()).hexdigest()


def get_seen_alerts(seen_alerts_file: Path = SEEN_ALERTS_CACHE) -> set[str]:
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


def main() -> None:
    seen_alerts: set[str] = get_seen_alerts()
    feed = feedparser.parse(NOAA_RSS_FEED_URL)

    for item in feed["entries"]:
        # Check skip based on ignore terms
        if check_skip(item):  # type: ignore
            logger.info(
                "Skipping product; title or summary contained unwanted term.",
                title=item["title"],
            )
            continue

        hash_ = get_hash(item)

        # Skip seen alerts
        if hash_ in seen_alerts:
            logger.info("Skipping previously seen product.", title=item["title"])
            continue

        # Check matches filter
        if not check_contains_term(SUMMARY_MUST_INCLUDE, item["summary"]):  # type: ignore
            logger.info(
                "Skipping product; summary did not include at least one necessary term.",
                terms=SUMMARY_MUST_INCLUDE,
            )
            continue

        # Cleanup summary text
        item["summary"] = cleanup_summary(item["summary"])  # type: ignore

        # Send notification
        try:
            notify_discord(item)
            seen_alerts.add(hash_)
        except Exception:
            logger.warning("Error sending message for product.", title=item["title"])

    store_seen_alerts(seen_alerts)


if __name__ == "__main__":
    while True:
        main()
        sleep(60)
