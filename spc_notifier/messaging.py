import re
from functools import lru_cache

import httpx
import structlog
from stamina import retry

from spc_notifier.config import (
    LLM_CONFIG,
    WEBHOOKS,
)
from spc_notifier.filtering import check_passes_filters
from spc_notifier.models import LLMConfig, SpcProduct, WebhookConfig

logger = structlog.get_logger(__name__)

CLAUDE_API_CALL_HEADERS = {
    "x-api-key": LLM_CONFIG.claude_api_key,
    "Content-Type": "application/json",
    "Anthropic-Version": "2023-06-01",
}
CLEAN_HTML_REGEX = re.compile("<.*?>")
NUMBERED_LINE_REGEX = re.compile(r"^\d+\.")


class HashableDict(dict):
    def __hash__(self) -> int:
        return hash(frozenset(self))


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


def _build_claude_request(
    summary: str, llm_config: LLMConfig = LLM_CONFIG
) -> HashableDict:
    logger.debug("Building Claude request.")
    return HashableDict(
        {
            "model": llm_config.claude_model,
            "max_tokens": llm_config.claude_max_tokens,
            "system": llm_config.prompt,
            "messages": [
                {
                    "role": "user",
                    "content": summary,
                }
            ],
        }
    )


@retry(on=httpx.HTTPError, attempts=3)
@lru_cache(maxsize=32)
def _summarize_with_llm(request: HashableDict) -> str:
    assert all(item in request for item in ("model", "max_tokens", "messages"))
    logger.info("Requesting product summary from Claude", model=request["model"])

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers=CLAUDE_API_CALL_HEADERS,
        json=request,
        timeout=30,
    )

    response.raise_for_status()
    response_text = response.json()["content"][0]["text"]

    return _cleanup_llm_response(response_text)


def submit_for_notification(
    product: SpcProduct,
    webhook_configs: list[WebhookConfig] = WEBHOOKS,
) -> None:
    """Receives SPC products for notification, checking each against the configured
    webhooks and calling notification submission if they pass filters."""

    for whc in webhook_configs:
        if check_passes_filters(product, whc.filters):
            logger.info(
                "Product passed filters; sending notification.",
                product=product["title"],
                webhook=whc.url,
            )
            json = _prepare_discord_message(whc, product)
            _post_discord_message(whc.url, json)


def _prepare_discord_message(
    webhook_config: WebhookConfig,
    product: SpcProduct,
    enable_llm_summaries: bool = LLM_CONFIG.enable_llm_summaries,
    include_spc_summaries: bool = LLM_CONFIG.include_spc_summaries,
) -> dict[str, any]:
    """Prepare Discord message payload."""

    # Prepare message text
    # Begin with product title, preceded by user or role mention if configured
    message_text = (
        f"<@{webhook_config.ping_user_or_role_id}>\n**{product["title"]}**"
        if webhook_config.ping_user_or_role_id
        else f"**{product["title"]}**"
    )

    cleaned_summary = _cleanup_summary(product["summary"])  # Remove HTML tags, etc.

    # Generate a more concise summary of the product using an LLM if enabled
    if enable_llm_summaries:
        try:
            request_data = _build_claude_request(cleaned_summary)
            llm_summary = _summarize_with_llm(request_data)
            message_text += f"\n{llm_summary}"
        except Exception as e:  # noqa: BLE001
            logger.warning("Error generating summary with LLM.", error=str(e))

            # If summary generation fails, include original text
            include_spc_summaries = True

    # Prepare data payload
    data: dict = {}

    # Embed the original SPC summary or add a link
    if include_spc_summaries:
        data["embeds"] = [
            {
                "title": product["title"],
                "url": product["link"],
                "description": product["summary"],
            },
        ]
    else:
        data["embeds"] = [
            {
                "title": product["title"],
                "url": product["link"],
                "description": "Click to view the full SPC product information.",
            }
        ]

    data["content"] = message_text

    return data


@retry(on=httpx.HTTPError, attempts=3)
def _post_discord_message(webhook_url: str, json_: dict[str, any]) -> None:
    """Send a Discord message to the specified endpoint."""
    result = httpx.post(webhook_url, json=json_)

    result.raise_for_status()
