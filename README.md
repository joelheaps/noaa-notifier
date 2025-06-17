# SPC Notifier

Generates Discord alerts when the Storm Prediction Center (part of the National Weather Service) publishes or updates alerts.  Data is scraped from the RSS feed documented at https://www.spc.noaa.gov/aboutrss.html.

Notifications can be filtered to only include products and alerts that contain specific terms, and exclude products that match certain terms.

Optionally, an LLM (Claude) can be used to generate a summary of each alert, with an API key.

## Getting started

To get started, create a config.toml with fields including the webhook URL for an integration in your Discord channel, and optionally adjust any other settings (including alert/product filters).

Then, launch the application with Docker compose:
```bash
docker compose up -d --build
```

### Running locally
This project uses `uv` to manage dependencies.  Use one of the many installation methods at https://docs.astral.sh/uv/getting-started/installation/ to install `uv` (or simply `pip install uv`).

Then, run the application.
```bash
uv run python -m spc_notifier.main
```

### Setting up a development environment
Similar to the instructions for *Running locally* above, `uv` is a prerequisite.

Simply run `uv sync` to create a virtual environment with all project (including development) dependencies.
