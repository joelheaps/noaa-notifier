# NOAA Storm Prediction Center RSS feed URL.  This shouldn't change.
NOAA_RSS_FEED_URL = "https://www.spc.noaa.gov/products/spcrss.xml"

# Enter a webhook URL to send Discord notifications to your channel.
DISCORD_WEBHOOK_URL = ""

# Enable LLM-generated summaries for SPC products.
ENABLE_LLM_SUMMARIES = False
CLAUDE_API_KEY = ""
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"  # https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table

# Enter a user or role ID to ping when a Discord notification is sent (or leave empty).
# See https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID
DISCORD_PING_USER_OR_ROLE_ID = ""

# Stores most recently seen alerts to deduplicate notifications.
SEEN_ALERTS_CACHE = "./seen_alerts.json"

# All product entries with these terms in the title will be ignored.
TITLE_MUST_NOT_INCLUDE = ["No watches are valid", "Fire"]

# All product entries with these terms in the summary will be ignored.
SUMMARY_MUST_NOT_INCLUDE = ["HAS NOT BEEN ISSUED YET"]

# Product entries must contain at least one of these terms.  All other entries will be ignored.
SUMMARY_MUST_INCLUDE = ["Nebraska", "Iowa", "Oklahoma"]
