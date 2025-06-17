import logging
from pathlib import Path

import structlog
import tomli

from spc_notifier.models import LLMConfig, WebhookConfig

logger = structlog.get_logger(__name__)

with Path("config.toml").open("rb") as f:
    config = tomli.load(f)


NOAA_RSS_FEED_URL = config.get("noaa_rss_feed_url")
LLM_CONFIG = LLMConfig(**config.get("llm", {}))
CACHE_FILE = config.get("cache_file", "storage/seen_products.json")
__DEBUG_MODE = config.get("debug_mode", False)
LOG_MODE = logging.DEBUG if __DEBUG_MODE else logging.INFO
WEBHOOKS = [
    WebhookConfig.from_dict(webhook_config)
    for webhook_config in config["discord_webhooks"]
]
