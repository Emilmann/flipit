"""Scraper-Modul: Abfrage und Parsing von willhaben.at (MVP-2, Issue #2)."""

from flipit.scraper.models import Listing
from flipit.scraper.willhaben import (
    ScraperError,
    WillhabenScraper,
    parse_listings,
)

__all__ = ["Listing", "ScraperError", "WillhabenScraper", "parse_listings"]
