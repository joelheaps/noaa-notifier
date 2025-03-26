from pathlib import Path

import tomli

from spc_notifier.models import WebhookConfig

with Path("config.toml").open("rb") as f:
    config = tomli.load(f)

NOAA_RSS_FEED_URL = config.get("noaa_rss_feed_url")
ENABLE_LLM_SUMMARIES = config.get("enable_llm_summaries", False)
CLAUDE_API_KEY = config.get("claude_api_key", "")
CLAUDE_MODEL = config.get("claude_model", "")
SEEN_ALERTS_CACHE = config.get("seen_alerts_cache", "storage/seen_alerts.json")
WEBHOOKS = [
    WebhookConfig(**webhook_config) for webhook_config in config["discord_webhooks"]
]
