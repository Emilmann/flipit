"""Marktwert-/Margen-Schätzung aus Vergleichsinseraten (MVP-7, Issue #12).

Schätzt den Marktwert eines Fahrzeugs aus vergleichbaren Inseraten desselben
Modells (km-/Baujahr-Korridor) als Median der Vergleichspreise und leitet daraus
eine Margen-Kennzahl (geschätzter Wert − Kaufpreis) ab. Diese fließt als
eigener Faktor in das Risiko-Scoring (MVP-4) ein.

Reine, deterministische Logik ohne Netzwerkzugriff → offline testbar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from statistics import median

from flipit.processing.models import CarDetail


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ValuationConfig:
    """Konfigurierbare Schwellen für die Vergleichswert-Schätzung."""

    min_sample_size: int = 3      # Mindestzahl Vergleichsinserate (ohne das Inserat selbst)
    mileage_tolerance: int = 40_000  # zulässige km-Abweichung zum Vergleich
    year_tolerance: int = 2        # zulässige Baujahr-Abweichung zum Vergleich

    @classmethod
    def from_env(cls) -> "ValuationConfig":
        return cls(
            min_sample_size=_env_int("VALUATION_MIN_SAMPLE", 3),
            mileage_tolerance=_env_int("VALUATION_MILEAGE_TOLERANCE", 40_000),
            year_tolerance=_env_int("VALUATION_YEAR_TOLERANCE", 2),
        )


@dataclass(frozen=True)
class ValuationResult:
    """Ergebnis der Marktwert-Schätzung für ein Inserat."""

    estimated_value: int       # geschätzter Marktwert (Median der Vergleichspreise)
    sample_size: int           # Anzahl genutzter Vergleichsinserate
    margin: int | None         # geschätzter Wert − Kaufpreis (None, wenn Preis fehlt)
    margin_pct: float | None   # margin / estimated_value (None, wenn Preis fehlt)


def _comparable(car: CarDetail, other: CarDetail, config: ValuationConfig) -> bool:
    """Prüft, ob `other` ein gültiges Vergleichsinserat zu `car` ist."""
    if other.id == car.id or other.price is None:
        return False
    if not car.make or not car.model:
        return False
    if (other.make or "").lower() != car.make.lower():
        return False
    if (other.model or "").lower() != car.model.lower():
        return False
    if car.mileage is not None and other.mileage is not None:
        if abs(other.mileage - car.mileage) > config.mileage_tolerance:
            return False
    if car.year is not None and other.year is not None:
        if abs(other.year - car.year) > config.year_tolerance:
            return False
    return True


class MarketValuator:
    """Schätzt Marktwerte aus einem Korpus von Inseraten."""

    def __init__(
        self,
        listings: list[CarDetail],
        config: ValuationConfig | None = None,
    ) -> None:
        self.listings = listings
        self.config = config or ValuationConfig()

    def estimate(self, car: CarDetail) -> ValuationResult | None:
        """Schätzt den Marktwert eines Inserats.

        Liefert `None`, wenn zu wenige Vergleichsinserate vorhanden sind
        (definierte neutrale Behandlung im Scoring/Dashboard).
        """
        comps = [o for o in self.listings if _comparable(car, o, self.config)]
        if len(comps) < self.config.min_sample_size:
            return None

        estimated = int(median(sorted(o.price for o in comps)))  # type: ignore[arg-type]
        margin: int | None = None
        margin_pct: float | None = None
        if car.price is not None and estimated > 0:
            margin = estimated - car.price
            margin_pct = margin / estimated

        return ValuationResult(
            estimated_value=estimated,
            sample_size=len(comps),
            margin=margin,
            margin_pct=margin_pct,
        )
