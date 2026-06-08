"""Persistenz der extrahierten Inserate via SQLite (MVP-3, Issue #3).

SQLite (stdlib `sqlite3`) statt JSON: keine zusätzliche Abhängigkeit, robuste
Wiederladbarkeit nach Neustart und abfragbar für das Dashboard (MVP-5). Bild-Pfade
werden als JSON-Liste in einer Spalte abgelegt; Upsert über die Inserat-`id`
verhindert Duplikate.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from pathlib import Path

from flipit.core.config import Settings, settings
from flipit.processing.models import CarDetail

# In CarDetail als JSON-Liste gespeicherte Felder.
_LIST_FIELDS = {"image_urls", "image_paths"}
# Bool-Felder: SQLite kennt keinen Bool-Typ → als 0/1 abgelegt, beim Lesen zurückwandeln.
_BOOL_FIELDS = {"is_private"}
# Nur persistierte (gespeicherte) Felder – berechnete Properties wie power_ps zählen nicht.
_COLUMNS = [f.name for f in fields(CarDetail)]


def _row_to_car(row: sqlite3.Row) -> CarDetail:
    data = dict(row)
    for key in _LIST_FIELDS:
        data[key] = json.loads(data[key]) if data.get(key) else []
    for key in _BOOL_FIELDS:
        if data.get(key) is not None:
            data[key] = bool(data[key])
    return CarDetail(**data)


class ListingRepository:
    """Speichert und lädt `CarDetail`-Datensätze in einer SQLite-Datenbank."""

    def __init__(self, config: Settings = settings) -> None:
        self.db_path = Path(config.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        # Spalten ohne Typ-Affinität (NONE) bewahren int/str/None beim Roundtrip.
        columns = ", ".join(
            f"{name} TEXT PRIMARY KEY" if name == "id" else name
            for name in _COLUMNS
        )
        with self._connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS listings ({columns})")

    def save(self, car: CarDetail) -> None:
        """Fügt ein Inserat ein oder aktualisiert es (Upsert über `id`)."""
        values = []
        for name in _COLUMNS:
            value = getattr(car, name)
            values.append(json.dumps(value) if name in _LIST_FIELDS else value)
        placeholders = ", ".join("?" for _ in _COLUMNS)
        col_list = ", ".join(_COLUMNS)
        updates = ", ".join(f"{c}=excluded.{c}" for c in _COLUMNS if c != "id")
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO listings ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                values,
            )

    def save_many(self, cars: list[CarDetail]) -> int:
        for car in cars:
            self.save(car)
        return len(cars)

    def get(self, listing_id: str) -> CarDetail | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
        return _row_to_car(row) if row else None

    def all(self) -> list[CarDetail]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM listings ORDER BY price").fetchall()
        return [_row_to_car(row) for row in rows]

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
