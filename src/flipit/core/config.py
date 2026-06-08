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


@dataclass(frozen=True)
class Settings:
    """Gebündelte Laufzeit-Konfiguration der Anwendung."""

    app_title: str
    data_dir: Path
    image_dir: Path


def load_settings() -> Settings:
    """Baut die Settings aus Umgebungsvariablen (mit Defaults)."""
    data_dir = _env_path("DATA_DIR", PROJECT_ROOT / "data")
    image_dir = _env_path("IMAGE_DIR", data_dir / "images")
    return Settings(
        app_title=os.getenv("APP_TITLE", "Flipit"),
        data_dir=data_dir,
        image_dir=image_dir,
    )


# Modul-weite Singleton-Instanz für bequemen Import: `from flipit.core.config import settings`
settings = load_settings()
