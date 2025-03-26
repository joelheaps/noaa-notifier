import re
from functools import lru_cache

import httpx
import structlog
from stamina import retry

from spc_notifier.config import (
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    ENABLE_LLM_SUMMARIES,
    WEBHOOKS,
)
from spc_notifier.models import SpcProduct, TermFilters, WebhookConfig

logger = structlog.get_logger()

CLAUDE_MAX_TOKENS = 1024
CLAUDE_API_CALL_HEADERS = {
    "x-api-key": CLAUDE_API_KEY,
    "Content-Type": "application/json",
    "Anthropic-Version": "2023-06-01",
}
CLAUDE_PROMPT = (
    "Summarize this National Weather Service Storm Prediction Center text concisely."
)
CLEAN_HTML_REGEX = re.compile("<.*?>")
NUMBERED_LINE_REGEX = re.compile(r"^\d+\.")


def _cleanup_summary(string_: str) -> str:
    """Remove HTML tags and related content from product summary."""
    cleaned = re.sub(CLEAN_HTML_REGEX, "", string_)
    cleaned = cleaned.replace("Read more", "")
    return cleaned.strip()


def _cleanup_llm_response(response_text: str) -> str:
    # Drop first line if it begins with a heading
    if response_text.startswith("#"):
        response_text = "\n".join(response_text.split("\n")[1:])

    # Drop next (first) line if it contains the word "summary"
    _first_line = response_text.split("\n")[0]
    if "summary" in _first_line.lower():
        response_text = "\n".join(response_text.split("\n")[1:])

    # Add an extra newline after lines starting with a number (Discord formatting issue)
    response_text = "\n".join(
        [
            line + "\n" if re.match(NUMBERED_LINE_REGEX, line) else line
            for line in response_text.split("\n")
        ]
    )

    return response_text.strip()


def _check_contains_terms(terms: list[str], string_: str) -> bool:
    """Check if string contains at least one of the terms provided."""
    string_ = string_.lower()
    return any(term.lower() in string_ for term in terms)


def _check_passes_filters(
    product: SpcProduct,
    filters: TermFilters,
) -> bool:
    """Determines whether an entry contains wanted and unwanted terms."""
    # Check title and summary contain at least one necessary term each
    title_include_ok = (
        _check_contains_terms(filters.title_must_include_one, product.title)
        if filters.title_must_include_one
        else True
    )
    title_exclude_ok = (
        not _check_contains_terms(filters.title_must_exclude_all, product.title)
        if filters.title_must_exclude_all
        else True
    )

    summary_include_ok = (
        _check_contains_terms(filters.summary_must_include_one, product.summary)
        if filters.summary_must_include_one
        else True
    )
    summary_exclude_ok = (
        not _check_contains_terms(filters.summary_must_exclude_all, product.summary)
        if filters.summary_must_exclude_all
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
        title_must_include_one="pass" if title_include_ok else "fail",
        title_must_exclude_all="pass" if title_exclude_ok else "fail",
        summary_must_include_one="pass" if summary_include_ok else "fail",
        summary_must_exclude_all="pass" if summary_exclude_ok else "fail",
    )
    return False


@lru_cache(maxsize=32)
@retry(on=httpx.HTTPError, attempts=3)
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
        headers=CLAUDE_API_CALL_HEADERS,
        json=data,
        timeout=30,
    )

    response.raise_for_status()
    response_text = response.json()["content"][0]["text"]

    return _cleanup_llm_response(response_text)


def _build_message_text(title: str, summary: str, ping_id: str) -> str:
    # Begin with product title, preceded by user or role mention if configured
    message_text = f"<@{ping_id}>\n**{title}**" if ping_id else f"**{title}**"

    # Generate a more concise summary using an LLM if enabled
    if ENABLE_LLM_SUMMARIES:
        try:
            summary = _summarize_with_llm(summary)
            message_text += f"\n{summary}"
        except Exception as e:  # noqa: BLE001
            logger.warning("Error generating summary with LLM.", error=str(e))
    return message_text


def submit_for_notification(
    product: SpcProduct,
    webhook_configs: list[WebhookConfig] = WEBHOOKS,
) -> None:
    """Receives SPC products for notification, checking each against the configured
    webhooks and calling notification submission if they pass filters."""

    for whc in webhook_configs:
        if _check_passes_filters(product, whc.filters):
            json = _prepare_discord_message(whc, product)
            _post_discord_message(whc.url, json)


def _prepare_discord_message(
    webhook_config: WebhookConfig,
    product: SpcProduct,
) -> dict[str, any]:
    """Prepare and send a Discord message to the specified endpoint."""
    summary = _cleanup_summary(product.summary)  # Remove HTML tags
    message_text = _build_message_text(
        product.title, product.summary, webhook_config.ping_user_or_role_id
    )

    return {
        "content": message_text,
        "embeds": [
            {
                "title": product.title,
                "url": product.link,
                "description": summary,
            },
        ],
    }


@retry(on=httpx.HTTPError, attempts=3)
def _post_discord_message(webhook_url: str, json_: dict[str, any]) -> None:
    """Send a Discord message to the specified endpoint."""
    result = httpx.post(webhook_url, json=json_)

    result.raise_for_status()
