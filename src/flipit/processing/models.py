"""Datenmodell der Detail-Extraktion (MVP-3, Issue #3).

`CarDetail` bündelt die vollständigen Metadaten eines willhaben-Inserats inkl.
Bild-Referenzen. Aufbauend auf der Trefferliste des Scrapers (MVP-2) und
Grundlage für Scoring (MVP-4) und Dashboard (MVP-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CarDetail:
    """Vollständige Metadaten eines Fahrzeug-Inserats."""

    id: str
    url: str                         # Quell-URL der Detailseite
    title: str = ""
    make: str | None = None          # Marke
    model: str | None = None         # Modell
    model_spec: str | None = None    # Modell-Spezifikation
    price: int | None = None         # Preis in Euro
    mileage: int | None = None       # Kilometerstand
    year: int | None = None          # Baujahr
    month: int | None = None         # Erstzulassungs-Monat
    power_kw: int | None = None       # Leistung in kW (ENGINE/EFFECT)
    fuel: str | None = None          # Kraftstoff
    transmission: str | None = None  # Getriebe
    engine_volume: int | None = None  # Hubraum in cm³
    car_type: str | None = None      # Karosserieform
    color: str | None = None         # Außenfarbe
    owners: int | None = None        # Anzahl Vorbesitzer
    description: str = ""            # bereinigter Beschreibungstext
    location: str | None = None
    postcode: str | None = None
    seller: str | None = None
    is_private: bool | None = None
    image_urls: list[str] = field(default_factory=list)   # Quell-URLs der Bilder
    image_paths: list[str] = field(default_factory=list)  # lokale Pfade nach Download
    image_score: float | None = None  # Bildqualitäts-/Auffälligkeits-Score 0–1 (MVP-6)
    model_risk_score: float | None = None   # Modellspezifisches Risiko 0–1 (MVP-8)
    model_risk_notes: str | None = None     # Begründung des Modell-Risikos (MVP-8)
    scraped_at: str | None = None    # ISO-Zeitstempel der Extraktion

    @property
    def power_ps(self) -> int | None:
        """Leistung in PS (gerundet), abgeleitet aus kW."""
        if self.power_kw is None:
            return None
        return round(self.power_kw * 1.35962)
