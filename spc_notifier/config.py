import logging
from pathlib import Path

import structlog
import tomli

from spc_notifier.models import TermFilters, WebhookConfig

logger = structlog.get_logger(__name__)

with Path("config.toml").open("rb") as f:
    config = tomli.load(f)


def _parse_webhook_config(webhook_config: dict) -> WebhookConfig:
    webhook_config["filters"] = TermFilters(**webhook_config.get("filters", {}))
    return WebhookConfig(**webhook_config)


NOAA_RSS_FEED_URL = config.get("noaa_rss_feed_url")
ENABLE_LLM_SUMMARIES = config.get("enable_llm_summaries", False)
INCLUDE_SPC_SUMMARIES = config.get("include_spc_summaries", True)
CLAUDE_API_KEY = config.get("claude_api_key", "")
CLAUDE_MODEL = config.get("claude_model", "")
CACHE_FILE = config.get("cache_file", "storage/seen_products.json")
__DEBUG_MODE = config.get("debug_mode", False)
LOG_MODE = logging.DEBUG if __DEBUG_MODE else logging.INFO
WEBHOOKS = [
    _parse_webhook_config(webhook_config)
    for webhook_config in config["discord_webhooks"]
]

if not ENABLE_LLM_SUMMARIES and not INCLUDE_SPC_SUMMARIES:
    logger.warning(
        "Both 'enable_llm_summaries' and 'include_spc_summaries' were disabled. Enabling 'include_spc_summaries' so notifications aren't empty."
    )
    INCLUDE_SPC_SUMMARIES = True
