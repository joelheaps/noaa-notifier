import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import httpx
import msgspec
import schedule
import structlog
from lxml import html

logger = structlog.get_logger()

MD_URL: str = "https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/spc_mesoscale_discussion"
MAPSERVER_QUERY_SUFFIX: str = "/MapServer/0/query?where=1%3D1&outFields=*&f=json"
DISCORD_WEBHOOK_URL: str = "https://discord.com/api/webhooks/1253666120813117460/3YfZNBfIxc_ETSMguKFWgmdJ5s73fprYRwSOGrX31n2YGe4N_ctmDxgdlHa_kxgfjjDw"


class MesoscaleDiscussion(msgspec.Struct):
    """Weather product data."""

    id: int
    info_page: str
    geometry: dict
    first_seen: datetime = datetime.now(tz=UTC)

    @classmethod
    def from_json(cls, data: dict) -> Self | None:
        """Create a new WxProduct from JSON data."""
        if data["attributes"]["name"] == "NoArea":
            return None
        return cls(
            id=int(data["attributes"]["name"].replace("MD ", "")),
            info_page=data["attributes"]["popupinfo"].replace("http", "https"),
            geometry=data["geometry"],
        )

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MesoscaleDiscussion):
            return NotImplemented
        return self.id == other.id

    def get_text(self) -> str:
        """Gets discussion text from html."""
        response = httpx.get(self.info_page)
        response.raise_for_status()
        tree = html.fromstring(response.text)
        elements = tree.xpath("//pre")
        return elements[0].text_content()


def get_md_objects() -> set[MesoscaleDiscussion]:
    """Returns a list of mesoscale discussions."""
    logger.info("Getting Mesoscale Discussions from NOAA map service")
    response = httpx.get(MD_URL + MAPSERVER_QUERY_SUFFIX)
    response.raise_for_status()
    if response.json()["features"]:
        wx_products = {
            MesoscaleDiscussion.from_json(md) for md in response.json()["features"]
        }
        return {wx_product for wx_product in wx_products if wx_product}  # Filter Nones
    return set()


class MdDb:
    def __init__(self) -> None:
        self.db_file = "md_db.json"
        self.md_db = self.load_md_db()

    def load_md_db(self) -> set[MesoscaleDiscussion]:
        try:
            with Path(self.db_file).open("rb") as f:
                return set(
                    msgspec.json.decode(f.read(), type=list[MesoscaleDiscussion]),
                )
        except FileNotFoundError:
            return set()

    def save_md_db(self) -> None:
        with Path(self.db_file).open("wb") as f:
            f.write(msgspec.json.encode(list(self.md_db)))

    def add_md(self, md: MesoscaleDiscussion) -> None:
        self.md_db.add(md)
        self.save_md_db()


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
    md_db = MdDb()
    new_mds = {md for md in get_md_objects() if md not in md_db.md_db}
    for md in new_mds:
        logger.info("New Mesoscale Discussion", md_id=md.id, info_page=md.info_page)
        md_db.add_md(md)
        notify_discord(md)

    if not new_mds:
        logger.info("No new MDs found")


if __name__ == "__main__":
    # Run every minute
    schedule.every().minute.do(main)
    while True:
        schedule.run_pending()
        time.sleep(1)
