"""Zentrale, env-getriebene Konfiguration für Flipit.

Keine Hardcoded-Werte im Code (vgl. claude.md, §Sicherheit). Alle Pfade und
Einstellungen werden aus der Umgebung gelesen und haben sinnvolle Defaults, damit
das Projekt auch ohne vollständige `.env` lokal startet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# `.env` einmalig beim Import laden (überschreibt keine bereits gesetzten Env-Vars).
load_dotenv()

# Projekt-Wurzel: .../flipit (drei Ebenen über dieser Datei: core -> flipit -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _env_path(key: str, default: Path) -> Path:
    """Liest einen Pfad aus der Umgebung; relative Pfade sind zur Projekt-Wurzel."""
    raw = os.getenv(key)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _env_list(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Liest eine kommaseparierte Liste aus der Umgebung (leere Einträge entfallen)."""
    raw = os.getenv(key)
    if not raw:
        return default
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    return items or default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Gebündelte Laufzeit-Konfiguration der Anwendung."""

    app_title: str
    data_dir: Path
    image_dir: Path
    db_path: Path                   # SQLite-Datei für persistierte Inserate (MVP-3)

    # --- Scraper (MVP-2) ---
    search_models: tuple[str, ...]  # vordefinierte Fahrzeugmodelle (Such-Keywords)
    price_min: int                  # Budget-Untergrenze in Euro
    price_max: int                  # Budget-Obergrenze in Euro
    willhaben_base_url: str         # Basis-URL der Gebrauchtwagen-Suche
    request_delay: float            # Pause zwischen Requests (freundliches Rate-Limiting)
    request_timeout: int            # HTTP-Timeout pro Request in Sekunden
    user_agent: str                 # User-Agent-Header für Requests

    # --- Modell-Risiko (MVP-8 / MVP-9) ---
    google_api_key: str             # Google API Key: Gemini LLM + Custom Search (MVP-8/9)
    google_cse_id: str              # Google Custom Search Engine ID (MVP-9)

    # --- Supabase (Cloud-Persistenz) ---
    supabase_url: str               # Supabase Project URL (leer → SQLite-Fallback)
    supabase_key: str               # Supabase service_role Key


def load_settings() -> Settings:
    """Baut die Settings aus Umgebungsvariablen (mit Defaults)."""
    data_dir = _env_path("DATA_DIR", PROJECT_ROOT / "data")
    image_dir = _env_path("IMAGE_DIR", data_dir / "images")
    db_path = _env_path("DB_PATH", data_dir / "flipit.db")
    return Settings(
        app_title=os.getenv("APP_TITLE", "Flipit"),
        data_dir=data_dir,
        image_dir=image_dir,
        db_path=db_path,
        search_models=_env_list("SEARCH_MODELS", ("Audi A3", "VW Golf", "BMW 3er")),
        price_min=_env_int("PRICE_MIN", 6000),
        price_max=_env_int("PRICE_MAX", 8000),
        willhaben_base_url=os.getenv(
            "WILLHABEN_BASE_URL",
            "https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenboerse",
        ),
        request_delay=_env_float("REQUEST_DELAY", 2.0),
        request_timeout=_env_int("REQUEST_TIMEOUT", 20),
        user_agent=os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        ),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        google_cse_id=os.getenv("GOOGLE_CSE_ID", ""),
        supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
        supabase_key=os.getenv("SUPABASE_KEY", "").strip(),
    )


# Modul-weite Singleton-Instanz für bequemen Import: `from flipit.core.config import settings`
settings = load_settings()
