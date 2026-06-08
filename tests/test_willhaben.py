"""Offline-Tests für den willhaben-Scraper (MVP-2, Issue #2).

Alle Tests laufen gegen eine gespeicherte HTML-Fixture – kein Live-Call.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from flipit.core.config import load_settings, settings
from flipit.scraper import Listing, ScraperError, WillhabenScraper, parse_listings

FIXTURE = Path(__file__).parent / "fixtures" / "willhaben_search.html"


@pytest.fixture
def search_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_returns_all_listings(search_html: str) -> None:
    listings = parse_listings(search_html, search_term="Audi A3")
    assert len(listings) == 3
    assert all(isinstance(item, Listing) for item in listings)


def test_parse_extracts_basic_fields(search_html: str) -> None:
    audi = next(item for item in parse_listings(search_html) if item.make == "Audi")
    assert audi.id == "1228790209"
    assert audi.title == "Audi A3 Daylight 2,0 TDI S-tronic"
    assert audi.price == 7450
    assert audi.year == 2014
    assert audi.mileage == 225800
    assert audi.model == "A3"
    assert audi.location == "Marchtrenk"
    assert audi.postcode == "4614"
    assert audi.is_private is False


def test_parse_builds_absolute_detail_url(search_html: str) -> None:
    listing = parse_listings(search_html)[0]
    assert listing.url.startswith("https://www.willhaben.at/iad/gebrauchtwagen/d/auto/")


def test_search_term_is_propagated(search_html: str) -> None:
    listings = parse_listings(search_html, search_term="VW Golf")
    assert all(item.search_term == "VW Golf" for item in listings)


def test_all_prices_within_budget_fixture(search_html: str) -> None:
    # Die Fixture stammt aus einer 6.000–8.000-€-Suche.
    prices = [item.price for item in parse_listings(search_html)]
    assert all(6000 <= price <= 8000 for price in prices if price is not None)


def test_missing_next_data_raises() -> None:
    with pytest.raises(ScraperError):
        parse_listings("<html><body>kein script</body></html>")


def test_empty_result_returns_empty_list() -> None:
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"searchResult":{}}}}'
        "</script>"
    )
    assert parse_listings(html) == []


def test_build_search_url_uses_config() -> None:
    cfg = replace(settings, price_min=6000, price_max=8000)
    scraper = WillhabenScraper(config=cfg)
    url = scraper.build_search_url("Audi A3")
    assert "keyword=Audi+A3" in url
    assert "PRICE_FROM=6000" in url
    assert "PRICE_TO=8000" in url
    assert url.startswith(cfg.willhaben_base_url)


def test_search_model_uses_stubbed_session(search_html: str) -> None:
    """search_model darf ohne Netzwerk laufen, wenn fetch gestubbt ist."""

    class _StubScraper(WillhabenScraper):
        def fetch(self, url: str) -> str:  # type: ignore[override]
            self.requested_url = url
            return search_html

    scraper = _StubScraper()
    listings = scraper.search_model("Audi A3")
    assert len(listings) == 3
    assert "keyword=Audi+A3" in scraper.requested_url
    assert all(item.search_term == "Audi A3" for item in listings)


def test_search_all_dedupes_and_skips_failures(search_html: str) -> None:
    cfg = replace(settings, search_models=("Audi A3", "VW Golf", "Kaputt"), request_delay=0.0)

    class _StubScraper(WillhabenScraper):
        def fetch(self, url: str) -> str:  # type: ignore[override]
            if "Kaputt" in url:
                raise ScraperError("simulierter Abruf-Fehler")
            return search_html

    listings = _StubScraper(config=cfg).search_all()
    # Zwei erfolgreiche Modelle liefern dieselben 3 Inserate → dedupliziert auf 3.
    assert len(listings) == 3
    assert len({item.id for item in listings}) == 3


def test_env_driven_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_MODELS", "Opel Astra, Ford Focus")
    monkeypatch.setenv("PRICE_MIN", "5000")
    monkeypatch.setenv("PRICE_MAX", "7000")
    cfg = load_settings()
    assert cfg.search_models == ("Opel Astra", "Ford Focus")
    assert cfg.price_min == 5000
    assert cfg.price_max == 7000
