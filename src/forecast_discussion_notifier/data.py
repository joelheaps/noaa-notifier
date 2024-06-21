from datetime import UTC, datetime
from typing import Self

import httpx
from lxml import html
from pydantic import BaseModel


class MesoscaleDiscussion(BaseModel):
    """Weather product data."""

    id: int
    info_page: str
    geometry: dict
    first_seen: datetime = datetime.now(tz=UTC)

    @classmethod
    def from_mapserver_json(cls, data: dict) -> Self | None:
        """Create a new MesoscaleDiscussion from NOAA ESRI map server JSON data."""
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
