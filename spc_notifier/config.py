from pathlib import Path

import tomli

from spc_notifier.models import WebhookConfig

with Path("config.toml").open("rb") as f:
    config = tomli.load(f)

NOAA_RSS_FEED_URL = config["noaa_rss_feed_url"]
ENABLE_LLM_SUMMARIES = config["enable_llm_summaries"]
CLAUDE_API_KEY = config["claude_api_key"]
CLAUDE_MODEL = config["claude_model"]
SEEN_ALERTS_CACHE = config["seen_alerts_cache"]
WEBHOOKS = [WebhookConfig(**webhook_config) for webhook_config in config["discord_webhooks"]]
