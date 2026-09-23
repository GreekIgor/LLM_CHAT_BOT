import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class ComplaintRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    address TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    description TEXT NOT NULL,
                    external_reference TEXT
                )
                """
            )

    def save(
        self,
        *,
        address: str,
        contact: str,
        description: str,
        external_reference: object | None,
    ) -> int:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO complaints (created_at, address, contact, description, external_reference)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    address,
                    contact,
                    description,
                    json.dumps(external_reference, ensure_ascii=False) if external_reference else None,
                ),
            )
            return int(cursor.lastrowid)
