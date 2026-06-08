"""Risiko-/Margen-Scoring-Engine (MVP-4, Issue #4).

Berechnet aus den extrahierten Metadaten eines `CarDetail` einen Gesamt-Score
(0–100) sowie einen **nachvollziehbaren Breakdown** der Einzelbeiträge. Jeder
Faktor wird auf [0, 1] normalisiert (1 = beste Bewertung / geringstes Risiko),
mit einem konfigurierbaren Gewicht multipliziert und aufsummiert.

Die Gewichte und Schwellen sind über `ScoringConfig` konfigurierbar (env-getrieben,
nicht hardcoded). Die UI (MVP-5) kann den Breakdown direkt anzeigen, um
darzustellen, wie sich die Gewichtungen zusammensetzen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from flipit.processing.models import CarDetail

# Neutraler Score, wenn ein Metadatenfeld fehlt (verzerrt das Ergebnis nicht).
_NEUTRAL = 0.5

_DEFAULT_NEGATIVE = (
    "unfall", "defekt", "motorschaden", "bastler", "export",
    "getriebeschaden", "ersatzteil", "pickerl fällig", "reparaturbedürftig",
)
_DEFAULT_POSITIVE = (
    "scheckheft", "garantie", "pickerl neu", "neue", "service",
    "unfallfrei", "nichtraucher", "top zustand", "gepflegt",
)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(key)
    if not raw:
        return default
    items = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    return items or default


@dataclass(frozen=True)
class ScoringConfig:
    """Konfigurierbares Gewichtungs- und Schwellen-Schema."""

    # Gewichte der Faktoren (werden intern auf Summe 1 normalisiert)
    weight_margin: float = 0.30       # Marge zum geschätzten Marktwert (MVP-7)
    weight_price: float = 0.10        # Budget-Headroom (sekundär)
    weight_mileage: float = 0.20
    weight_age: float = 0.10
    weight_description: float = 0.15
    weight_images: float = 0.15       # Bildqualität/-plausibilität (MVP-6)

    # Budget-Range (Budget-Headroom): günstiger innerhalb des Budgets = besser
    price_min: int = 6000
    price_max: int = 8000

    # Marge zum Marktwert (margin_pct): best = Score 1.0, worst = Score 0.0
    margin_best_pct: float = 0.20     # 20 % unter Marktwert = bestes Geschäft
    margin_worst_pct: float = -0.15   # 15 % über Marktwert = schlechtestes

    # Kilometerstand: best = Score 1.0, worst = Score 0.0
    mileage_best: int = 50_000
    mileage_worst: int = 250_000

    # Alter in Jahren: best = Score 1.0, worst = Score 0.0
    age_best: int = 0
    age_worst: int = 20
    reference_year: int = field(
        default_factory=lambda: datetime.now(timezone.utc).year
    )

    # Beschreibungs-Signale
    negative_keywords: tuple[str, ...] = _DEFAULT_NEGATIVE
    positive_keywords: tuple[str, ...] = _DEFAULT_POSITIVE
    keyword_step: float = 0.2  # Score-Änderung pro Treffer (ausgehend von 0.5)

    @classmethod
    def from_env(cls) -> "ScoringConfig":
        """Lädt die Konfiguration aus Umgebungsvariablen (mit Defaults)."""
        return cls(
            weight_margin=_env_float("SCORE_WEIGHT_MARGIN", 0.30),
            weight_price=_env_float("SCORE_WEIGHT_PRICE", 0.10),
            weight_mileage=_env_float("SCORE_WEIGHT_MILEAGE", 0.20),
            weight_age=_env_float("SCORE_WEIGHT_AGE", 0.10),
            weight_description=_env_float("SCORE_WEIGHT_DESCRIPTION", 0.15),
            weight_images=_env_float("SCORE_WEIGHT_IMAGES", 0.15),
            price_min=_env_int("PRICE_MIN", 6000),
            price_max=_env_int("PRICE_MAX", 8000),
            margin_best_pct=_env_float("SCORE_MARGIN_BEST_PCT", 0.20),
            margin_worst_pct=_env_float("SCORE_MARGIN_WORST_PCT", -0.15),
            mileage_best=_env_int("SCORE_MILEAGE_BEST", 50_000),
            mileage_worst=_env_int("SCORE_MILEAGE_WORST", 250_000),
            age_best=_env_int("SCORE_AGE_BEST", 0),
            age_worst=_env_int("SCORE_AGE_WORST", 20),
            reference_year=_env_int("SCORE_REFERENCE_YEAR", datetime.now(timezone.utc).year),
            negative_keywords=_env_list("SCORE_NEGATIVE_KEYWORDS", _DEFAULT_NEGATIVE),
            positive_keywords=_env_list("SCORE_POSITIVE_KEYWORDS", _DEFAULT_POSITIVE),
            keyword_step=_env_float("SCORE_KEYWORD_STEP", 0.2),
        )

    @property
    def weights(self) -> dict[str, float]:
        return {
            "margin": self.weight_margin,
            "price": self.weight_price,
            "mileage": self.weight_mileage,
            "age": self.weight_age,
            "description": self.weight_description,
            "images": self.weight_images,
        }


@dataclass(frozen=True)
class FactorScore:
    """Beitrag eines einzelnen Faktors zum Gesamt-Score."""

    name: str
    raw_value: object          # Ausgangswert (z. B. Preis, km) – None falls unbekannt
    normalized: float          # auf [0, 1] normalisiert (1 = beste Bewertung)
    weight: float              # normalisiertes Gewicht
    contribution: float        # normalized * weight (Beitrag zum Gesamtwert)


@dataclass(frozen=True)
class ScoreResult:
    """Gesamtergebnis: Score (0–100) plus transparenter Breakdown."""

    listing_id: str
    total: float
    factors: tuple[FactorScore, ...]

    def explain(self) -> str:
        """Menschenlesbare Aufschlüsselung der Score-Zusammensetzung."""
        lines = [f"Gesamt-Score: {self.total:.1f}/100"]
        for f in self.factors:
            lines.append(
                f"  {f.name:12} roh={f.raw_value!s:>10} "
                f"norm={f.normalized:.2f} × Gewicht={f.weight:.2f} "
                f"→ {f.contribution * 100:.1f}"
            )
        return "\n".join(lines)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _linear(value: float, best: float, worst: float) -> float:
    """Lineare Normalisierung: best → 1.0, worst → 0.0 (geclamped)."""
    if best == worst:
        return _NEUTRAL
    return _clamp((worst - value) / (worst - best))


class RiskScorer:
    """Berechnet Risiko-/Margen-Scores für Inserate."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig()

    def _score_margin(
        self, car: CarDetail, market_value: float | None
    ) -> tuple[object, float]:
        # Marge zum geschätzten Marktwert; ohne Marktwert/Preis neutral.
        if market_value is None or market_value <= 0 or car.price is None:
            return None, _NEUTRAL
        margin_pct = (market_value - car.price) / market_value
        normalized = _linear(
            margin_pct, self.config.margin_best_pct, self.config.margin_worst_pct
        )
        return f"{margin_pct * 100:+.0f}%", normalized

    def _score_price(self, car: CarDetail) -> tuple[object, float]:
        if car.price is None:
            return None, _NEUTRAL
        # Budget-Headroom: günstiger innerhalb des Budgets = besser.
        return car.price, _linear(car.price, self.config.price_min, self.config.price_max)

    def _score_mileage(self, car: CarDetail) -> tuple[object, float]:
        if car.mileage is None:
            return None, _NEUTRAL
        return car.mileage, _linear(
            car.mileage, self.config.mileage_best, self.config.mileage_worst
        )

    def _score_age(self, car: CarDetail) -> tuple[object, float]:
        if car.year is None:
            return None, _NEUTRAL
        age = self.config.reference_year - car.year
        return age, _linear(age, self.config.age_best, self.config.age_worst)

    def _score_description(self, car: CarDetail) -> tuple[object, float]:
        text = (car.description or "").lower()
        if not text:
            return None, _NEUTRAL
        negatives = sum(1 for kw in self.config.negative_keywords if kw in text)
        positives = sum(1 for kw in self.config.positive_keywords if kw in text)
        score = _NEUTRAL + (positives - negatives) * self.config.keyword_step
        return f"+{positives}/-{negatives}", _clamp(score)

    def _score_images(self, car: CarDetail) -> tuple[object, float]:
        # Bild-Score (MVP-6) ist bereits auf [0, 1] normalisiert; ohne neutral.
        if car.image_score is None:
            return None, _NEUTRAL
        return round(car.image_score, 2), _clamp(car.image_score)

    def score(self, car: CarDetail, market_value: float | None = None) -> ScoreResult:
        """Berechnet Gesamt-Score und Breakdown für ein Inserat.

        `market_value` (geschätzter Marktwert, MVP-7) speist den Margen-Faktor;
        fehlt er, wird die Marge neutral bewertet.
        """
        raw_weights = self.config.weights
        total_weight = sum(raw_weights.values()) or 1.0

        scorers = {
            "margin": lambda c: self._score_margin(c, market_value),
            "price": self._score_price,
            "mileage": self._score_mileage,
            "age": self._score_age,
            "description": self._score_description,
            "images": self._score_images,
        }

        factors: list[FactorScore] = []
        total = 0.0
        for name, scorer in scorers.items():
            raw_value, normalized = scorer(car)
            weight = raw_weights[name] / total_weight  # auf Summe 1 normalisiert
            contribution = normalized * weight
            total += contribution
            factors.append(
                FactorScore(
                    name=name,
                    raw_value=raw_value,
                    normalized=round(normalized, 4),
                    weight=round(weight, 4),
                    contribution=round(contribution, 4),
                )
            )

        return ScoreResult(
            listing_id=car.id,
            total=round(total * 100, 1),
            factors=tuple(factors),
        )
