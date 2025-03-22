# SPC Notifier

Generates Discord alerts when the Storm Prediction Center (part of the National Weather Service) publishes or updates alerts.  Data is scraped from the RSS feed documented at https://www.spc.noaa.gov/aboutrss.html.

Notifications can be filtered to only include products and alerts that contain specific terms, and exclude products that match certain terms.

Optionally, an LLM (Claude) can be used to generate a summary of each alert, with an API key.

## Getting started

To get started, rename `config_example.py` to `config.py`, fill in the webhook URL for an integration in your Discord channel, and optionally adjust any other settings (including alert/product filters).

Then, launch the application with Docker compose:
```bash
docker compose up -d --build
```

To run without Docker, install the required dependencies and run the application:
```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m spc_notifier.main # --loop
```
