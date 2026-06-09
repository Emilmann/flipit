"""Verarbeitungs-Pipeline: Detail-Extraktion, Bild-Download, Persistenz (MVP-3).

Verbindet die Bausteine: nimmt Inserate aus dem Scraper (MVP-2), lädt die
Detailseite, extrahiert die Metadaten (`parse_detail`), lädt optional die Bilder
(`download_images`) und persistiert das Ergebnis (`ListingRepository`).

Die reine, netzwerkfreie Verarbeitung steckt in `process_detail_html()` und ist
darüber offline testbar. `run()` orchestriert den vollständigen Lauf inkl.
Netzwerkzugriff.
"""

from __future__ import annotations

import logging

import requests

from flipit.core.config import Settings, settings
from flipit.processing.extract import parse_detail
from flipit.processing.image_analysis import analyze_paths
from flipit.processing.images import download_images
from flipit.processing.models import CarDetail
from flipit.processing.storage import ListingRepository
from flipit.scraper import Listing, WillhabenScraper

logger = logging.getLogger(__name__)


def process_detail_html(
    html: str,
    source_url: str,
    *,
    repo: ListingRepository,
    config: Settings = settings,
    session: requests.Session | None = None,
    download: bool = True,
) -> CarDetail:
    """Verarbeitet das HTML einer Detailseite zu einem persistierten `CarDetail`.

    Netzwerkzugriff erfolgt nur, wenn `download=True` und das Inserat Bild-URLs
    enthält – damit ist die Extraktions-/Persistenz-Logik offline testbar.
    """
    car = parse_detail(html, source_url=source_url)
    if download and car.image_urls:
        download_images(car, config=config, session=session)
        if car.image_paths:
            analysis = analyze_paths(car.image_paths)
            if analysis is not None:
                car.image_score = analysis.image_score
    if config.google_api_key:
        from flipit.processing.model_risk import ModelRiskLookup
        lookup = ModelRiskLookup(
            str(config.db_path),
            config.google_api_key,
            config.google_cse_id,
        )
        result = lookup.lookup(car)
        car.model_risk_score = result.score
        car.model_risk_notes = result.notes
    repo.save(car)
    return car


def run(
    config: Settings = settings,
    scraper: WillhabenScraper | None = None,
    repo: ListingRepository | None = None,
    download: bool = True,
) -> list[CarDetail]:
    """Vollständiger Lauf: Modelle suchen, Details extrahieren, persistieren."""
    scraper = scraper or WillhabenScraper(config=config)
    repo = repo or ListingRepository(config=config)

    listings: list[Listing] = scraper.search_all()
    logger.info("%d Inserate aus der Suche – verarbeite Details.", len(listings))

    results: list[CarDetail] = []
    for listing in listings:
        if not listing.url:
            continue
        try:
            html = scraper.fetch(listing.url)
            car = process_detail_html(
                html,
                listing.url,
                repo=repo,
                config=config,
                session=scraper.session,
                download=download,
            )
        except Exception:  # robust: ein Fehler darf den Lauf nicht abbrechen
            logger.exception("Verarbeitung fehlgeschlagen: %s", listing.url)
            continue
        results.append(car)

    logger.info("%d Inserate verarbeitet und persistiert.", len(results))
    return results
