"""Bild-Download für Inserate (MVP-3, Issue #3).

Lädt die Bilder eines `CarDetail` in ein lokales, pro-Inserat getrenntes
Verzeichnis unterhalb von `settings.image_dir` (Pfad via `.env`) und referenziert
die lokalen Pfade im Datensatz.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from flipit.core.config import Settings, settings
from flipit.processing.models import CarDetail

logger = logging.getLogger(__name__)


def _extension(url: str, default: str = ".jpg") -> str:
    suffix = Path(url.split("?")[0]).suffix
    return suffix if suffix else default


def download_images(
    car: CarDetail,
    config: Settings = settings,
    session: requests.Session | None = None,
) -> list[str]:
    """Lädt alle Bilder eines Inserats lokal herunter.

    Speichert nach `<image_dir>/<id>/<n><ext>` und schreibt die lokalen Pfade in
    `car.image_paths`. Bereits vorhandene Dateien werden übersprungen
    (idempotent). Einzelne fehlgeschlagene Downloads werden geloggt und
    übersprungen, statt den ganzen Vorgang abzubrechen.
    """
    http = session or requests.Session()
    target_dir = Path(config.image_dir) / car.id
    target_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    for index, url in enumerate(car.image_urls, start=1):
        dest = target_dir / f"{index}{_extension(url)}"
        if dest.exists():
            paths.append(str(dest))
            continue
        try:
            response = http.get(url, timeout=config.request_timeout)
            response.raise_for_status()
            dest.write_bytes(response.content)
        except requests.RequestException:
            logger.exception("Bild-Download fehlgeschlagen: %s", url)
            continue
        paths.append(str(dest))

    car.image_paths = paths
    return paths
