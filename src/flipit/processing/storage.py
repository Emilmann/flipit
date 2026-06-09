"""Persistenz der extrahierten Inserate – SQLite (lokal) oder Supabase (Cloud).

SQLite bleibt der lokale Fallback (keine zusätzliche Abhängigkeit, immer verfügbar).
Sind SUPABASE_URL und SUPABASE_KEY gesetzt, wechselt `create_repository()` automatisch
auf `SupabaseListingRepository` – Postgres mit JSONB für Listen und nativen Bool/Int-Typen.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from pathlib import Path

from flipit.core.config import Settings, settings
from flipit.processing.models import CarDetail

# In CarDetail als JSON-Liste gespeicherte Felder (SQLite-spezifisch).
_LIST_FIELDS = {"image_urls", "image_paths"}
# Bool-Felder: SQLite kennt keinen Bool-Typ → als 0/1 abgelegt, beim Lesen zurückwandeln.
_BOOL_FIELDS = {"is_private"}
# Nur persistierte Felder – berechnete Properties wie power_ps zählen nicht.
_COLUMNS = [f.name for f in fields(CarDetail)]


def _row_to_car(row: sqlite3.Row) -> CarDetail:
    data = dict(row)
    for key in _LIST_FIELDS:
        data[key] = json.loads(data[key]) if data.get(key) else []
    for key in _BOOL_FIELDS:
        if data.get(key) is not None:
            data[key] = bool(data[key])
    return CarDetail(**data)


def _car_to_record(car: CarDetail) -> dict:
    """Wandelt CarDetail in ein Supabase-kompatibles dict um (Listen + Bool nativ)."""
    record = {}
    for name in _COLUMNS:
        value = getattr(car, name)
        record[name] = value if value is not None else None
    # Leere Listen statt None für JSONB-Spalten
    for key in _LIST_FIELDS:
        if record[key] is None:
            record[key] = []
    return record


def _record_to_car(record: dict) -> CarDetail:
    """Wandelt ein Supabase-Response-dict in CarDetail um."""
    data = dict(record)
    for key in _LIST_FIELDS:
        if data.get(key) is None:
            data[key] = []
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
        columns = ", ".join(
            f"{name} TEXT PRIMARY KEY" if name == "id" else name
            for name in _COLUMNS
        )
        with self._connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS listings ({columns})")
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(listings)")}
            for name in _COLUMNS:
                if name not in existing:
                    conn.execute(f"ALTER TABLE listings ADD COLUMN {name}")

    def save(self, car: CarDetail) -> None:
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


class SupabaseListingRepository:
    """Speichert und lädt `CarDetail`-Datensätze in Supabase (Postgres/JSONB)."""

    def __init__(self, config: Settings) -> None:
        from supabase import create_client
        self._client = create_client(config.supabase_url, config.supabase_key)

    def save(self, car: CarDetail) -> None:
        self._client.table("listings").upsert(_car_to_record(car)).execute()

    def save_many(self, cars: list[CarDetail]) -> int:
        if not cars:
            return 0
        records = [_car_to_record(c) for c in cars]
        self._client.table("listings").upsert(records).execute()
        return len(records)

    def get(self, listing_id: str) -> CarDetail | None:
        resp = self._client.table("listings").select("*").eq("id", listing_id).execute()
        return _record_to_car(resp.data[0]) if resp.data else None

    def all(self) -> list[CarDetail]:
        resp = self._client.table("listings").select("*").order("price").execute()
        return [_record_to_car(r) for r in resp.data]

    def count(self) -> int:
        resp = (
            self._client.table("listings")
            .select("*", count="exact")
            .limit(0)
            .execute()
        )
        return resp.count or 0


def create_repository(config: Settings = settings) -> ListingRepository | SupabaseListingRepository:
    """Factory: Supabase wenn konfiguriert, sonst SQLite-Fallback."""
    if config.supabase_url and config.supabase_key:
        return SupabaseListingRepository(config)
    return ListingRepository(config)
