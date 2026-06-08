"""Deterministische Tests der Marktwert-/Margen-Schätzung (MVP-7, Issue #12)."""

from __future__ import annotations

from dataclasses import replace

from flipit.processing import CarDetail, MarketValuator, ValuationConfig

CFG = ValuationConfig(min_sample_size=3, mileage_tolerance=40_000, year_tolerance=2)


def car(id_: str, *, make="Audi", model="A3", price=7000, mileage=150_000, year=2016) -> CarDetail:
    return CarDetail(id=id_, url=f"u/{id_}", title=f"{make} {model}",
                     make=make, model=model, price=price, mileage=mileage, year=year)


def _corpus() -> list[CarDetail]:
    # Vier vergleichbare Audi A3 (Preise 6000/7000/8000/9000) + ein fremdes Modell.
    return [
        car("a", price=6000),
        car("b", price=7000),
        car("c", price=8000),
        car("d", price=9000),
        car("x", make="BMW", model="3er", price=7500),
    ]


def test_estimates_median_of_comparables() -> None:
    target = car("t", price=6500)
    valuator = MarketValuator(_corpus() + [target], CFG)
    result = valuator.estimate(target)
    assert result is not None
    # Median von 6000/7000/8000/9000 = 7500.
    assert result.estimated_value == 7500
    assert result.sample_size == 4


def test_margin_is_value_minus_price() -> None:
    target = car("t", price=6000)
    result = MarketValuator(_corpus() + [target], CFG).estimate(target)
    assert result is not None
    assert result.margin == 7500 - 6000
    assert result.margin_pct == (7500 - 6000) / 7500


def test_returns_none_below_min_sample() -> None:
    target = car("t")
    # Nur zwei Vergleichswerte → unter min_sample_size (3).
    small = [car("a", price=6000), car("b", price=7000), target]
    assert MarketValuator(small, CFG).estimate(target) is None


def test_excludes_self_from_comparables() -> None:
    target = car("b", price=7000)  # selbe id wie ein Korpus-Eintrag
    result = MarketValuator(_corpus(), CFG).estimate(target)
    # 'b' wird als sich selbst ausgeschlossen → nur a/c/d (3 Vergleiche).
    assert result is not None
    assert result.sample_size == 3


def test_only_same_make_and_model_count() -> None:
    target = car("t", make="BMW", model="3er", price=7000)
    # Korpus hat nur EINEN BMW 3er (x) → zu wenige Vergleiche.
    assert MarketValuator(_corpus() + [target], CFG).estimate(target) is None


def test_mileage_tolerance_filters_out() -> None:
    target = car("t", mileage=150_000, price=7000)
    far = [
        car("a", mileage=300_000, price=6000),
        car("b", mileage=310_000, price=6500),
        car("c", mileage=320_000, price=7000),
    ]
    # Alle weit außerhalb der km-Toleranz → keine Vergleiche.
    assert MarketValuator(far + [target], CFG).estimate(target) is None


def test_year_tolerance_respected() -> None:
    target = car("t", year=2016, price=7000)
    valuator = MarketValuator(
        [car("a", year=2016, price=6000), car("b", year=2017, price=7000),
         car("c", year=2015, price=8000), car("d", year=2009, price=3000),  # zu alt
         target],
        CFG,
    )
    result = valuator.estimate(target)
    assert result is not None
    # 'd' (2009) fällt raus → Median von 6000/7000/8000 = 7000.
    assert result.estimated_value == 7000
    assert result.sample_size == 3


def test_missing_make_model_yields_none() -> None:
    target = CarDetail(id="t", url="u/t", title="?", make=None, model=None, price=7000)
    assert MarketValuator(_corpus() + [target], CFG).estimate(target) is None


def test_from_env(monkeypatch) -> None:
    monkeypatch.setenv("VALUATION_MIN_SAMPLE", "5")
    monkeypatch.setenv("VALUATION_MILEAGE_TOLERANCE", "10000")
    cfg = ValuationConfig.from_env()
    assert cfg.min_sample_size == 5
    assert cfg.mileage_tolerance == 10_000
