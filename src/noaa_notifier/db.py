import json
import sqlite3
from datetime import datetime

from noaa_notifier.data import MesoscaleDiscussion


class DatabaseHandler:
    def __init__(self, db_name: str) -> None:
        """Initializes the database connection and creates the table if it doesn't exist."""
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self) -> None:
        """Creates the MesoscaleDiscussion table if it doesn't exist."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS MesoscaleDiscussion (
                id INTEGER PRIMARY KEY,
                info_page TEXT,
                geometry TEXT,
                first_seen TEXT
            )
            """
        )
        self.conn.commit()

    def add_md(self, md: MesoscaleDiscussion) -> None:
        data: dict = md.model_dump(mode="json")

        data["geometry"] = json.dumps(
            data["geometry"]
        )  # Convert geometry to JSON string
        data["first_seen"] = data["first_seen"]
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO MesoscaleDiscussion (id, info_page, geometry, first_seen)
            VALUES (:id, :info_page, :geometry, :first_seen)
            """,
            data,
        )
        self.conn.commit()

    def get_mds(self) -> set[MesoscaleDiscussion]:
        self.cursor.execute("SELECT * FROM MesoscaleDiscussion")
        rows = self.cursor.fetchall()
        discussions: set[MesoscaleDiscussion] = set()
        for row in rows:
            data = {
                "id": row[0],
                "info_page": row[1],
                "geometry": json.loads(row[2]),
                "first_seen": datetime.fromisoformat(row[3]),
            }
            discussions.add(MesoscaleDiscussion(**data))
        return discussions

    def close(self) -> None:
        self.conn.close()
