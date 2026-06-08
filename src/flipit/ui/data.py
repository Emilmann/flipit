"""Datenschicht des Dashboards (MVP-5, Issue #5).

Verbindet persistierte Inserate (MVP-3) mit der Scoring-Engine (MVP-4) und stellt
reine, testbare Hilfsfunktionen zum Laden, Filtern und Sortieren bereit. Die
Streamlit-Darstellung (`ui/dashboard.py`) baut hierauf auf.
"""

from __future__ import annotations

from dataclasses import dataclass

from flipit.processing import (
    CarDetail,
    ListingRepository,
    MarketValuator,
    RiskScorer,
    ScoreResult,
    ValuationResult,
)


@dataclass(frozen=True)
class ScoredListing:
    """Ein Inserat mit berechnetem Score und (falls vorhanden) Marktwert-Schätzung."""

    car: CarDetail
    score: ScoreResult
    valuation: ValuationResult | None = None

    @property
    def total(self) -> float:
        return self.score.total


def load_scored_listings(
    repo: ListingRepository,
    scorer: RiskScorer | None = None,
    valuator: MarketValuator | None = None,
) -> list[ScoredListing]:
    """Lädt alle persistierten Inserate, schätzt Marktwerte und berechnet Scores.

    Der Marktwert (MVP-7) wird aus dem gesamten geladenen Korpus geschätzt und
    speist den Margen-Faktor des Scorers.
    """
    scorer = scorer or RiskScorer()
    cars = repo.all()
    valuator = valuator or MarketValuator(cars)

    items: list[ScoredListing] = []
    for car in cars:
        valuation = valuator.estimate(car)
        market_value = valuation.estimated_value if valuation else None
        items.append(
            ScoredListing(
                car=car,
                score=scorer.score(car, market_value=market_value),
                valuation=valuation,
            )
        )
    return items


def filter_listings(
    items: list[ScoredListing],
    *,
    max_price: int | None = None,
    min_score: float | None = None,
    search: str | None = None,
) -> list[ScoredListing]:
    """Filtert nach Preis-Obergrenze, Mindest-Score und Freitext (Titel)."""
    result = items
    if max_price is not None:
        result = [i for i in result if i.car.price is not None and i.car.price <= max_price]
    if min_score is not None:
        result = [i for i in result if i.total >= min_score]
    if search:
        needle = search.lower()
        result = [i for i in result if needle in (i.car.title or "").lower()]
    return result


# Erlaubte Sortierschlüssel → (Zugriffs-Funktion, absteigend?)
_SORT_KEYS = {
    "Score (hoch→niedrig)": (lambda i: i.total, True),
    "Preis (niedrig→hoch)": (lambda i: i.car.price if i.car.price is not None else float("inf"), False),
    "Kilometerstand (niedrig→hoch)": (lambda i: i.car.mileage if i.car.mileage is not None else float("inf"), False),
    "Baujahr (neu→alt)": (lambda i: i.car.year if i.car.year is not None else -1, True),
}

SORT_OPTIONS = tuple(_SORT_KEYS.keys())


def sort_listings(items: list[ScoredListing], key: str) -> list[ScoredListing]:
    """Sortiert die Inserate nach einem der `SORT_OPTIONS`."""
    accessor, reverse = _SORT_KEYS.get(key, _SORT_KEYS[SORT_OPTIONS[0]])
    return sorted(items, key=accessor, reverse=reverse)
