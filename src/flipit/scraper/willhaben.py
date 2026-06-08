"""Willhaben-Scraper – Basis-Logik (MVP-2, Issue #2).

Fragt die willhaben.at-Gebrauchtwagensuche nach vordefinierten Modellen ab und
liefert die Trefferliste als `Listing`-Objekte zurück.

willhaben ist eine Next.js-App: die Suchergebnisse stecken als JSON im
`__NEXT_DATA__`-Script der Seite (Pfad
`props.pageProps.searchResult.advertSummaryList.advertSummary[]`). Das Parsen
dieses JSON ist robuster als CSS-Selektoren gegen wechselndes Markup, daher wird
`requests` genutzt; Selenium ist nicht nötig.

Konfiguration kommt ausschließlich aus `core.config` (keine Hardcoded-Werte).
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlencode

import requests

from flipit.core.config import Settings, settings
from flipit.scraper.models import Listing

logger = logging.getLogger(__name__)

# Detail-Seiten leiten sich aus dem relativen SEO_URL-Attribut ab.
_DETAIL_BASE = "https://www.willhaben.at/iad/"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


class ScraperError(RuntimeError):
    """Fehler beim Abruf oder Parsen einer willhaben-Suchseite."""


def _extract_next_data(html: str) -> dict[str, Any]:
    """Liest das eingebettete `__NEXT_DATA__`-JSON aus dem HTML."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise ScraperError("Kein __NEXT_DATA__-Script in der Seite gefunden.")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensiv
        raise ScraperError(f"__NEXT_DATA__-JSON nicht parsebar: {exc}") from exc


def _attr_map(ad: dict[str, Any]) -> dict[str, str]:
    """Wandelt die Attribut-Liste eines Inserats in ein flaches name→value-Dict."""
    result: dict[str, str] = {}
    for attr in ad.get("attributes", {}).get("attribute", []):
        name = attr.get("name")
        values = attr.get("values")
        if not name or not values:
            continue
        result[name] = values[0]
    return result


def _to_int(raw: str | None) -> int | None:
    """Parst einen Integer aus willhaben-Strings (ignoriert Nicht-Ziffern)."""
    if raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def _build_listing(ad: dict[str, Any], search_term: str) -> Listing:
    """Baut ein `Listing` aus einem rohen advertSummary-Eintrag."""
    attrs = _attr_map(ad)
    seo_url = attrs.get("SEO_URL", "")
    url = _DETAIL_BASE + seo_url.lstrip("/") if seo_url else ""
    is_private_raw = attrs.get("ISPRIVATE")

    return Listing(
        id=str(ad.get("id", "")),
        title=attrs.get("HEADING") or ad.get("description") or "",
        url=url,
        search_term=search_term,
        price=_to_int(attrs.get("PRICE")),
        year=_to_int(attrs.get("YEAR_MODEL")),
        mileage=_to_int(attrs.get("MILEAGE")),
        make=attrs.get("CAR_MODEL/MAKE"),
        model=attrs.get("CAR_MODEL/MODEL"),
        location=attrs.get("LOCATION"),
        postcode=attrs.get("POSTCODE"),
        seller=attrs.get("ORGNAME"),
        is_private=(is_private_raw == "1") if is_private_raw is not None else None,
    )


def parse_listings(html: str, search_term: str = "") -> list[Listing]:
    """Extrahiert alle Inserate einer willhaben-Suchergebnis-Seite.

    Reine Funktion ohne Netzwerkzugriff – Grundlage der Offline-Tests.
    """
    data = _extract_next_data(html)
    try:
        ads = (
            data["props"]["pageProps"]["searchResult"]
            ["advertSummaryList"]["advertSummary"]
        )
    except (KeyError, TypeError):
        # Struktur vorhanden, aber ohne Treffer → leere Liste statt Fehler.
        return []
    return [_build_listing(ad, search_term) for ad in ads if isinstance(ad, dict)]


class WillhabenScraper:
    """Abruf & Parsing der willhaben-Gebrauchtwagensuche.

    Beispiel:
        >>> scraper = WillhabenScraper()
        >>> listings = scraper.search_all()
    """

    def __init__(
        self,
        config: Settings = settings,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.user_agent,
                "Accept-Language": "de-AT,de;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def build_search_url(self, keyword: str) -> str:
        """Baut die Such-URL für ein Modell innerhalb der Budget-Range."""
        params = {
            "keyword": keyword,
            "PRICE_FROM": self.config.price_min,
            "PRICE_TO": self.config.price_max,
        }
        return f"{self.config.willhaben_base_url}?{urlencode(params)}"

    def fetch(self, url: str) -> str:
        """Lädt eine Seite mit Timeout und Fehlerbehandlung."""
        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(f"Abruf fehlgeschlagen für {url}: {exc}") from exc
        return response.text

    def search_model(self, keyword: str) -> list[Listing]:
        """Sucht ein einzelnes Modell und liefert die gefundenen Inserate."""
        url = self.build_search_url(keyword)
        logger.info("Suche willhaben nach %r → %s", keyword, url)
        html = self.fetch(url)
        listings = parse_listings(html, search_term=keyword)
        logger.info("%d Inserate für %r gefunden.", len(listings), keyword)
        return listings

    def search_all(self) -> list[Listing]:
        """Sucht alle konfigurierten Modelle und entfernt ID-Duplikate.

        Zwischen den Modell-Abfragen wird `request_delay` pausiert
        (freundliches Rate-Limiting). Schlägt ein einzelnes Modell fehl, wird
        es geloggt und übersprungen, statt den ganzen Lauf abzubrechen.
        """
        seen: set[str] = set()
        results: list[Listing] = []
        for index, keyword in enumerate(self.config.search_models):
            if index > 0 and self.config.request_delay > 0:
                time.sleep(self.config.request_delay)
            try:
                listings = self.search_model(keyword)
            except ScraperError:
                logger.exception("Modell-Suche fehlgeschlagen: %r", keyword)
                continue
            for listing in listings:
                if listing.id and listing.id not in seen:
                    seen.add(listing.id)
                    results.append(listing)
        return results
