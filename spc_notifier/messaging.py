import re

import httpx
import structlog
from feedparser import FeedParserDict

from spc_notifier.config import (
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    DISCORD_PING_USER_OR_ROLE_ID,
    DISCORD_WEBHOOK_URL,
    ENABLE_LLM_SUMMARIES,
)

logger = structlog.get_logger()


CLEAN_HTML_REGEX = re.compile("<.*?>")
CLAUDE_MAX_TOKENS = 1024
__CLAUDE_API_CALL_HEADERS = {
    "x-api-key": CLAUDE_API_KEY,
    "Content-Type": "application/json",
    "Anthropic-Version": "2023-06-01",
}
CLAUDE_PROMPT = (
    "Summarize this National Weather Service Storm Prediction Center text concisely."
)


def _cleanup_summary(string_: str) -> str:
    cleaned = re.sub(CLEAN_HTML_REGEX, "", string_)
    cleaned = cleaned.replace("Read more", "")
    return cleaned.strip()


def _cleanup_llm_response(response_text: str) -> str:
    # Drop first line if it begins with a heading
    if response_text.startswith("#"):
        response_text = "\n".join(response_text.split("\n")[1:])

    # Drop first line if it contains the word "summary"
    _first_line = response_text.split("\n")[0]
    if "summary" in _first_line.lower():
        response_text = "\n".join(response_text.split("\n")[1:])

    # Add an extra newline after lines starting with a number (Discord formatting issue)
    response_text = "\n".join(
        [
            line + "\n" if re.match(r"^\d+\.", line) else line
            for line in response_text.split("\n")
        ]
    )

    return response_text.strip()


def _summarize_with_llm(summary: str) -> str:
    logger.info("Generating LLM summary using Claude", model=CLAUDE_MODEL)
    data = {
        "model": CLAUDE_MODEL,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": f"{CLAUDE_PROMPT}\n\n{summary}",
            }
        ],
    }

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers=__CLAUDE_API_CALL_HEADERS,
        json=data,
        timeout=30,
    )

    response.raise_for_status()
    response_text = response.json()["content"][0]["text"]

    return _cleanup_llm_response(response_text)


def get_message_text(title: str, summary: str) -> str:
    # Begin with product title, preceded by user or role mention if configured
    message_text = (
        f"<@{DISCORD_PING_USER_OR_ROLE_ID}>\n**{title}**"
        if DISCORD_PING_USER_OR_ROLE_ID
        else f"**{title}**"
    )

    # Generate a more concise summary using an LLM if enabled
    if ENABLE_LLM_SUMMARIES:
        try:
            summary = _summarize_with_llm(summary)
            message_text += f"\n{summary}"
        except Exception as e:  # noqa: BLE001
            logger.warning("Error generating summary with LLM.", error=str(e))
    return message_text


def send_discord_alert(
    entry: FeedParserDict,
    webhook_url: str = DISCORD_WEBHOOK_URL,
) -> None:
    """Sends Discord message containing summary and link to SPC alert."""
    logger.info(
        "Notifying Discord of new NOAA alert or product.", product=entry["title"]
    )

    summary = _cleanup_summary(entry["summary"])  # Remove HTML tags
    title = entry["title"]
    message_text = get_message_text(title, summary)

    result = httpx.post(
        webhook_url,
        json={
            "content": message_text,
            "embeds": [
                {
                    "title": title,
                    "url": entry["link"],
                    "description": summary,
                },
            ],
        },
    )

    result.raise_for_status()
