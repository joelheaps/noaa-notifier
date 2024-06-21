import time

import httpx
import schedule
import structlog

from forecast_discussion_notifier.data import MesoscaleDiscussion
from forecast_discussion_notifier.db import DatabaseHandler

logger = structlog.get_logger()

MD_URL: str = "https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/spc_mesoscale_discussion"
MAPSERVER_QUERY_SUFFIX: str = "/MapServer/0/query?where=1%3D1&outFields=*&f=json"
DISCORD_WEBHOOK_URL: str = "https://discord.com/api/webhooks/1253666120813117460/3YfZNBfIxc_ETSMguKFWgmdJ5s73fprYRwSOGrX31n2YGe4N_ctmDxgdlHa_kxgfjjDw"


def get_mds_from_noaa() -> set[MesoscaleDiscussion]:
    """Returns a list of mesoscale discussions."""
    logger.info("Getting Mesoscale Discussions from NOAA map service")
    response = httpx.get(MD_URL + MAPSERVER_QUERY_SUFFIX)
    response.raise_for_status()
    if response.json()["features"]:
        wx_products: set[MesoscaleDiscussion | None] = {
            MesoscaleDiscussion.from_mapserver_json(md)
            for md in response.json()["features"]
        }
        return {wx_product for wx_product in wx_products if wx_product}  # Filter Nones
    return set()


def notify_discord(
    md: MesoscaleDiscussion,
    webhook_url: str = DISCORD_WEBHOOK_URL,
) -> int:
    """Notifies Discord of a new mesoscale discussion."""
    logger.info("Notifying Discord of new MD", md_id=md.id)
    result = httpx.post(
        webhook_url,
        json={
            "content": f"New Mesoscale Discussion: {md.id}",
            "embeds": [
                {
                    "title": f"Mesoscale Discussion {md.id}",
                    "url": md.info_page,
                    "description": md.get_text(),
                },
            ],
        },
    )
    result.raise_for_status()
    return result.status_code


def main() -> None:
    db = DatabaseHandler("mesoscale_discussions.db")
    new_mds = {md for md in get_mds_from_noaa() if md not in db.get_mds()}
    for md in new_mds:
        logger.info("New Mesoscale Discussion", md_id=md.id, info_page=md.info_page)
        db.add_md(md)
        notify_discord(md)

    if not new_mds:
        logger.info("No new MDs found")


if __name__ == "__main__":
    # Run every minute
    logger.info("Starting notifier scheduler")
    schedule.every().minute.do(main)

    main()
    while True:
        schedule.run_pending()
        time.sleep(1)
