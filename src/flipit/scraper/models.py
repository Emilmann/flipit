"""Datenmodelle des Scrapers.

`Listing` bündelt die Basisdaten eines willhaben-Inserats aus der Trefferliste
(MVP-2). Die vertiefte Feld-Extraktion und Persistenz folgt in MVP-3 (Issue #3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Listing:
    """Ein einzelnes Inserat aus der willhaben-Suchergebnisliste."""

    id: str
    title: str
    url: str
    search_term: str           # Such-Keyword, über das dieses Inserat gefunden wurde
    price: int | None = None
    year: int | None = None
    mileage: int | None = None  # Kilometerstand
    make: str | None = None     # Marke
    model: str | None = None    # Modell
    location: str | None = None
    postcode: str | None = None
    seller: str | None = None
    is_private: bool | None = None
