import re

import httpx
import structlog
from feedparser import FeedParserDict

from spc_notifier.config import DISCORD_WEBHOOK_URL

logger = structlog.get_logger()


CLEAN_HTML_REGEX = re.compile("<.*?>")


def cleanup_summary(string_: str) -> str:
    cleaned = re.sub(CLEAN_HTML_REGEX, "", string_)
    cleaned = cleaned.replace("Read more", "")
    return cleaned.strip()


def send_discord_alert(
    entry: FeedParserDict,
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
