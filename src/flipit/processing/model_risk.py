"""Modellspezifisches Risiko-Lookup via NHTSA-API + EU Safety Gate (RAPEX) + Gemini (MVP-8/9).

Kombiniert:
- NHTSA REST-API: US-Rückrufdaten (Live-Abfrage pro Fahrzeug)
- EU Safety Gate (RAPEX): EU-Rückrufe als lokal gecachtes CSV (monatlicher Refresh)
- Google Custom Search: Foren-Snippets (motor-talk.de, auto.de, Reddit)
- Google Gemini: LLM-Bewertung bekannter Serienmängel, km-Risiken, Baujahr-Schwächen

Alle Ergebnisse werden mit 30-Tage-TTL in SQLite gecacht (gleiche DB wie Inserate).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from flipit.processing.models import CarDetail

logger = logging.getLogger(__name__)

_NHTSA_URL = "https://api.nhtsa.dot.gov/recalls/recallsByVehicle"
_RAPEX_CSV_URL = (
    "https://ec.europa.eu/safety-gate-alerts/screen/exportDataCSV?lang=en"
)
_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_FORUM_SITE_FILTER = (
    "site:motor-talk.de OR site:auto.de OR site:reddit.com/r/cars OR site:reddit.com/r/de"
)
_CACHE_TTL_DAYS = 30
_NEUTRAL_RESULT_INCOMPLETE = (0.5, "Unvollständige Fahrzeugdaten")
_NEUTRAL_RESULT_ERROR = (0.5, "Lookup fehlgeschlagen")

# Kategorie-Schlüsselwörter um Fahrzeug-Einträge aus dem RAPEX-Gesamt-CSV zu filtern.
_RAPEX_VEHICLE_KEYWORDS = frozenset({
    "motor vehicle", "motorfahrzeug", "kraftfahrzeug", "automobile",
    "motorcycle", "motorrad", "vehicle", "car ", "pkw", "kfz",
})

_LLM_SYSTEM = (
    "Du bist ein erfahrener KFZ-Sachverständiger mit umfangreichem Wissen über "
    "bekannte Modellprobleme, Serienmängel und typische Verschleißmuster europäischer "
    "und amerikanischer Fahrzeuge. Antworte ausschließlich mit validem JSON."
)

_LLM_USER_TEMPLATE = """\
Bewerte das Risikopotenzial dieses Fahrzeugs:

Marke: {make}
Modell: {model}
Baujahr: {year}
Kilometerstand: {mileage} km
Kraftstoff: {fuel}
Hubraum: {engine_volume} cm³

NHTSA-Rückrufe (USA, {nhtsa_count} gefunden):
{nhtsa_summary}

EU Safety Gate / RAPEX-Warnungen ({rapex_count} gefunden):
{rapex_summary}

Foren-Erfahrungsberichte ({forum_count} Snippets):
{forum_summary}

Kaufpreis: {price}
Geschätzter Marktwert: {market_value}

Berücksichtige bei der Bewertung:
1. Bekannte Serienmängel dieses Modells und Motortyps
2. Typische Verschleißprobleme bei diesem Kilometerstand
3. Baujahr-spezifische Schwachstellen (z.B. schlechte Produktionsjahrgänge)
4. Anzahl und Schwere der Rückrufe (NHTSA und EU)
5. Erfahrungen aus Foren (häufige Mängel, K.O.-Kriterien, Reparaturkomplexität)
6. Preis-Risiko-Verhältnis (Kaufpreis vs. Marktwert)

Antworte NUR mit diesem JSON (keine weiteren Erklärungen):
{{"score": 0.0, "notes": "..."}}

Dabei gilt: 1.0 = geringstes Risiko, 0.0 = höchstes Risiko.
"notes" enthält maximal 2 prägnante Sätze auf Deutsch.\
"""


@dataclass(frozen=True)
class ModelRiskResult:
    """Modellspezifisches Risiko eines Fahrzeugs."""

    score: float   # 0.0–1.0 (1.0 = geringstes Risiko)
    notes: str     # kurze Begründung auf Deutsch


def _cache_key(make: str, model: str, year: int, fuel: str, mileage_bucket: int) -> str:
    raw = f"{make.lower()}|{model.lower()}|{year}|{fuel.lower()}|{mileage_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()


class ModelRiskCache:
    """SQLite-backed Cache mit 30-Tage-TTL für Modell-Risiko-Ergebnisse."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS model_risk_cache ("
                "  cache_key TEXT PRIMARY KEY,"
                "  score REAL NOT NULL,"
                "  notes TEXT NOT NULL,"
                "  cached_at TEXT NOT NULL"
                ")"
            )

    def get(self, key: str) -> ModelRiskResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT score, notes, cached_at FROM model_risk_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        cached_at = datetime.fromisoformat(row["cached_at"])
        age_days = (datetime.now(timezone.utc) - cached_at).days
        if age_days >= _CACHE_TTL_DAYS:
            return None
        return ModelRiskResult(score=row["score"], notes=row["notes"])

    def set(self, key: str, result: ModelRiskResult) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO model_risk_cache (cache_key, score, notes, cached_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET score=excluded.score, "
                "notes=excluded.notes, cached_at=excluded.cached_at",
                (key, result.score, result.notes, now),
            )


class RapexCache:
    """Lokaler SQLite-Cache für EU Safety Gate (RAPEX) Fahrzeug-Warnungen.

    Lädt das RAPEX-Gesamt-CSV monatlich herunter, filtert Fahrzeug-Einträge
    und speichert sie in SQLite für schnelle Textsuche.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS rapex_alerts ("
                "  alert_id TEXT PRIMARY KEY,"
                "  brand TEXT,"
                "  product TEXT,"
                "  category TEXT,"
                "  risk_type TEXT,"
                "  measures TEXT,"
                "  alert_date TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS rapex_meta ("
                "  key TEXT PRIMARY KEY,"
                "  value TEXT"
                ")"
            )

    def _is_stale(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM rapex_meta WHERE key = 'last_updated'"
            ).fetchone()
        if row is None:
            return True
        last_updated = datetime.fromisoformat(row["value"])
        return (datetime.now(timezone.utc) - last_updated).days >= _CACHE_TTL_DAYS

    def refresh_if_stale(self) -> None:
        if not self._is_stale():
            return
        logger.info("Lade EU Safety Gate CSV herunter...")
        try:
            resp = requests.get(_RAPEX_CSV_URL, timeout=60)
            resp.raise_for_status()
            self._import_csv(resp.content)
            now = datetime.now(timezone.utc).isoformat()
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO rapex_meta (key, value) VALUES ('last_updated', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (now,),
                )
            logger.info("EU Safety Gate CSV erfolgreich importiert.")
        except Exception:
            logger.warning("EU Safety Gate CSV-Download fehlgeschlagen.", exc_info=True)

    def _import_csv(self, raw: bytes) -> None:
        # CSV kann UTF-8 oder Latin-1 sein; beide versuchen.
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            logger.warning("RAPEX CSV: unbekannte Kodierung, überspringe Import.")
            return

        reader = csv.DictReader(io.StringIO(text))
        rows: list[tuple] = []
        for row in reader:
            category = self._find_col(row, ("category", "produktkategorie", "catégorie")) or ""
            if not any(kw in category.lower() for kw in _RAPEX_VEHICLE_KEYWORDS):
                continue
            alert_id = self._find_col(row, ("alert number", "meldungsnummer", "numéro")) or ""
            brand = self._find_col(row, ("brand", "marke", "marque")) or ""
            product = self._find_col(row, ("product name", "produktname", "nom du produit", "product type")) or ""
            risk_type = self._find_col(row, ("risk type", "risikoart", "type de risque")) or ""
            measures = self._find_col(row, ("measures", "maßnahmen", "mesures")) or ""
            alert_date = self._find_col(row, ("date", "datum")) or ""
            if alert_id:
                rows.append((alert_id, brand, product, category, risk_type, measures, alert_date))

        with self._connect() as conn:
            conn.execute("DELETE FROM rapex_alerts")
            conn.executemany(
                "INSERT OR IGNORE INTO rapex_alerts "
                "(alert_id, brand, product, category, risk_type, measures, alert_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        logger.info("%d RAPEX-Fahrzeugwarnungen importiert.", len(rows))

    @staticmethod
    def _find_col(row: dict, candidates: tuple[str, ...]) -> str | None:
        """Findet einen Spaltenwert anhand alternativer Spaltennamen (case-insensitiv)."""
        lower_row = {k.lower().strip(): v for k, v in row.items() if k is not None}
        for candidate in candidates:
            if candidate in lower_row:
                return lower_row[candidate]
        return None

    def search(self, make: str, model: str) -> list[dict]:
        """Sucht RAPEX-Warnungen für eine Marke/Modell-Kombination."""
        pattern = f"%{make.lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT brand, product, risk_type, measures, alert_date "
                "FROM rapex_alerts "
                "WHERE lower(brand) LIKE ? OR lower(product) LIKE ?",
                (pattern, f"%{model.lower()}%"),
            ).fetchall()
        return [dict(r) for r in rows]


class ModelRiskLookup:
    """Ermittelt modellspezifisches Risiko via NHTSA + RAPEX + Foren + Gemini."""

    def __init__(
        self,
        db_path: str,
        google_api_key: str = "",
        google_cse_id: str = "",
    ) -> None:
        self._cache = ModelRiskCache(db_path)
        self._rapex = RapexCache(db_path)
        self._google_api_key = google_api_key
        self._google_cse_id = google_cse_id

    def lookup(self, car: CarDetail, market_value: float | None = None) -> ModelRiskResult:
        if not car.make or not car.model or not car.year:
            return ModelRiskResult(*_NEUTRAL_RESULT_INCOMPLETE)

        mileage = car.mileage or 0
        mileage_bucket = (mileage // 50_000) * 50_000
        key = _cache_key(
            car.make,
            car.model,
            car.year,
            car.fuel or "",
            mileage_bucket,
        )

        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Model-Risiko Cache-Hit für %s %s %s", car.make, car.model, car.year)
            return cached

        nhtsa_recalls = self._fetch_nhtsa_recalls(car.make, car.model, car.year)
        self._rapex.refresh_if_stale()
        rapex_alerts = self._rapex.search(car.make, car.model)
        forum_snippets = self._fetch_forum_snippets(
            car.make, car.model, car.year, car.fuel or ""
        )

        result = self._llm_score(car, nhtsa_recalls, rapex_alerts, forum_snippets, market_value)
        self._cache.set(key, result)
        return result

    def _fetch_nhtsa_recalls(self, make: str, model: str, year: int) -> list[dict]:
        try:
            resp = requests.get(
                _NHTSA_URL,
                params={"make": make, "model": model, "modelYear": year},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception:
            logger.warning("NHTSA-API nicht erreichbar für %s %s %s", make, model, year)
            return []

    def _fetch_forum_snippets(
        self, make: str, model: str, year: int, fuel: str
    ) -> list[dict]:
        if not self._google_api_key or not self._google_cse_id:
            return []
        query = f'({_FORUM_SITE_FILTER}) "{make} {model}" Mängel Probleme Erfahrung'
        try:
            resp = requests.get(
                _GOOGLE_CSE_URL,
                params={
                    "key": self._google_api_key,
                    "cx": self._google_cse_id,
                    "q": query,
                    "num": 5,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                {"title": i.get("title", ""), "snippet": i.get("snippet", "")}
                for i in items
            ]
        except Exception:
            logger.warning("Google CSE nicht erreichbar für %s %s", make, model)
            return []

    def _llm_score(
        self,
        car: CarDetail,
        nhtsa_recalls: list[dict],
        rapex_alerts: list[dict],
        forum_snippets: list[dict],
        market_value: float | None = None,
    ) -> ModelRiskResult:
        if not self._google_api_key:
            return ModelRiskResult(*_NEUTRAL_RESULT_ERROR)
        try:
            from google import genai
            from google.genai import types as genai_types

            mv_str = f"{market_value:,.0f} €" if market_value else "unbekannt"
            price_str = f"{car.price:,} €" if car.price else "unbekannt"

            prompt = _LLM_USER_TEMPLATE.format(
                make=car.make or "unbekannt",
                model=car.model or "unbekannt",
                year=car.year or "unbekannt",
                mileage=f"{car.mileage:,}" if car.mileage else "unbekannt",
                fuel=car.fuel or "unbekannt",
                engine_volume=car.engine_volume or "unbekannt",
                nhtsa_count=len(nhtsa_recalls),
                nhtsa_summary=self._format_nhtsa(nhtsa_recalls),
                rapex_count=len(rapex_alerts),
                rapex_summary=self._format_rapex(rapex_alerts),
                forum_count=len(forum_snippets),
                forum_summary=self._format_forum_snippets(forum_snippets),
                price=price_str,
                market_value=mv_str,
            )

            client = genai.Client(api_key=self._google_api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_LLM_SYSTEM,
                    max_output_tokens=256,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )
            raw = response.text.strip()
            # Gemini umschließt JSON manchmal mit ```json ... ``` — bereinigen.
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)
            return ModelRiskResult(
                score=max(0.0, min(1.0, float(data["score"]))),
                notes=str(data["notes"]),
            )
        except Exception:
            logger.warning(
                "LLM-Lookup fehlgeschlagen für %s %s", car.make, car.model, exc_info=True
            )
            return ModelRiskResult(*_NEUTRAL_RESULT_ERROR)

    @staticmethod
    def _format_nhtsa(recalls: list[dict]) -> str:
        if not recalls:
            return "Keine Rückrufe in der NHTSA-Datenbank gefunden."
        lines = []
        for r in recalls[:5]:
            component = r.get("component", "")
            summary = r.get("summary", r.get("consequenceSummary", ""))
            lines.append(f"- {component}: {summary[:120]}")
        if len(recalls) > 5:
            lines.append(f"... und {len(recalls) - 5} weitere Rückrufe.")
        return "\n".join(lines)

    @staticmethod
    def _format_rapex(alerts: list[dict]) -> str:
        if not alerts:
            return "Keine Warnungen im EU Safety Gate gefunden."
        lines = []
        for a in alerts[:5]:
            risk = a.get("risk_type", "")
            product = a.get("product", "")
            date = a.get("alert_date", "")
            lines.append(f"- {product} ({date}): {risk[:100]}")
        if len(alerts) > 5:
            lines.append(f"... und {len(alerts) - 5} weitere Warnungen.")
        return "\n".join(lines)

    @staticmethod
    def _format_forum_snippets(snippets: list[dict]) -> str:
        if not snippets:
            return "Keine Foren-Erfahrungsberichte gefunden."
        lines = []
        for s in snippets[:5]:
            title = s.get("title", "").strip()
            snippet = s.get("snippet", "").strip()
            lines.append(f"- {title}: {snippet[:150]}")
        if len(snippets) > 5:
            lines.append(f"... und {len(snippets) - 5} weitere Ergebnisse.")
        return "\n".join(lines)
