"""Deterministische Unit-Tests der Risiko-Scoring-Engine (MVP-4, Issue #4)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from flipit.processing import CarDetail, RiskScorer, ScoreResult, ScoringConfig

# Feste Referenz-Konfiguration → reproduzierbare Scores unabhängig vom Kalenderjahr.
CONFIG = ScoringConfig(reference_year=2025)


def make_car(**kwargs) -> CarDetail:
    base = dict(
        id="1",
        url="https://example.test/1",
        price=7000,
        mileage=150_000,
        year=2018,
        description="",
    )
    base.update(kwargs)
    return CarDetail(**base)


def test_score_is_deterministic() -> None:
    scorer = RiskScorer(CONFIG)
    car = make_car()
    assert scorer.score(car).total == scorer.score(car).total


def test_total_within_bounds() -> None:
    result = RiskScorer(CONFIG).score(make_car())
    assert 0.0 <= result.total <= 100.0


def test_breakdown_has_all_factors() -> None:
    result = RiskScorer(CONFIG).score(make_car())
    names = {f.name for f in result.factors}
    assert names == {"margin", "price", "mileage", "age", "description"}


def test_contributions_sum_to_total() -> None:
    result = RiskScorer(CONFIG).score(make_car())
    summed = sum(f.contribution for f in result.factors) * 100
    assert summed == pytest.approx(result.total, abs=0.5)


def test_weights_normalize_to_one() -> None:
    result = RiskScorer(CONFIG).score(make_car())
    assert sum(f.weight for f in result.factors) == pytest.approx(1.0, abs=1e-6)


def test_cheaper_car_scores_higher_on_price() -> None:
    scorer = RiskScorer(CONFIG)
    cheap = next(f for f in scorer.score(make_car(price=6000)).factors if f.name == "price")
    pricey = next(f for f in scorer.score(make_car(price=8000)).factors if f.name == "price")
    assert cheap.normalized > pricey.normalized


def test_lower_mileage_scores_higher() -> None:
    scorer = RiskScorer(CONFIG)
    low = next(f for f in scorer.score(make_car(mileage=50_000)).factors if f.name == "mileage")
    high = next(f for f in scorer.score(make_car(mileage=250_000)).factors if f.name == "mileage")
    assert low.normalized == pytest.approx(1.0)
    assert high.normalized == pytest.approx(0.0)


def test_newer_car_scores_higher_on_age() -> None:
    scorer = RiskScorer(CONFIG)
    new = next(f for f in scorer.score(make_car(year=2025)).factors if f.name == "age")
    old = next(f for f in scorer.score(make_car(year=2005)).factors if f.name == "age")
    assert new.normalized == pytest.approx(1.0)
    assert old.normalized == pytest.approx(0.0)


def test_negative_keywords_lower_description_score() -> None:
    scorer = RiskScorer(CONFIG)
    bad = next(
        f for f in scorer.score(make_car(description="Auto mit Motorschaden, Bastler")).factors
        if f.name == "description"
    )
    assert bad.normalized < 0.5


def test_positive_keywords_raise_description_score() -> None:
    scorer = RiskScorer(CONFIG)
    good = next(
        f for f in scorer.score(make_car(description="Scheckheft gepflegt, Pickerl neu")).factors
        if f.name == "description"
    )
    assert good.normalized > 0.5


def test_missing_fields_are_neutral() -> None:
    scorer = RiskScorer(CONFIG)
    result = scorer.score(make_car(price=None, mileage=None, year=None, description=""))
    for factor in result.factors:
        assert factor.raw_value is None
        assert factor.normalized == pytest.approx(0.5)
    assert result.total == pytest.approx(50.0, abs=0.5)


def test_weights_are_configurable() -> None:
    # Nur Preis zählt → Score = Preis-Normalisierung × 100.
    cfg = replace(
        CONFIG, weight_margin=0.0, weight_price=1.0, weight_mileage=0.0,
        weight_age=0.0, weight_description=0.0,
    )
    result = RiskScorer(cfg).score(make_car(price=6000))
    assert result.total == pytest.approx(100.0)


def test_margin_factor_rewards_below_market_price() -> None:
    scorer = RiskScorer(CONFIG)
    # Preis 6000, Marktwert 8000 → ~25 % unter Markt → hoher Margen-Score.
    good = next(
        f for f in scorer.score(make_car(price=6000), market_value=8000).factors
        if f.name == "margin"
    )
    # Preis 8000, Marktwert 7000 → über Markt → niedriger Margen-Score.
    bad = next(
        f for f in scorer.score(make_car(price=8000), market_value=7000).factors
        if f.name == "margin"
    )
    assert good.normalized > 0.9
    assert bad.normalized < 0.5
    assert good.normalized > bad.normalized


def test_margin_neutral_without_market_value() -> None:
    margin = next(
        f for f in RiskScorer(CONFIG).score(make_car(price=7000)).factors
        if f.name == "margin"
    )
    assert margin.raw_value is None
    assert margin.normalized == pytest.approx(0.5)


def test_market_value_raises_total_for_good_deal() -> None:
    scorer = RiskScorer(CONFIG)
    car = make_car(price=6000)
    without = scorer.score(car).total
    with_deal = scorer.score(car, market_value=9000).total  # deutlich unter Markt
    assert with_deal > without


def test_from_env_reads_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCORE_WEIGHT_PRICE", "0.5")
    monkeypatch.setenv("SCORE_MILEAGE_WORST", "300000")
    cfg = ScoringConfig.from_env()
    assert cfg.weight_price == 0.5
    assert cfg.mileage_worst == 300_000


def test_explain_is_readable() -> None:
    text = RiskScorer(CONFIG).score(make_car()).explain()
    assert "Gesamt-Score" in text
    assert "price" in text and "mileage" in text


def test_better_car_beats_worse_car() -> None:
    scorer = RiskScorer(CONFIG)
    good = make_car(price=6000, mileage=60_000, year=2022,
                    description="Scheckheft, unfallfrei, Pickerl neu")
    bad = make_car(price=8000, mileage=240_000, year=2008,
                   description="Bastlerfahrzeug mit Motorschaden")
    assert scorer.score(good).total > scorer.score(bad).total
