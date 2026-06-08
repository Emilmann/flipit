"""Offline-Tests der Dashboard-Datenschicht (MVP-5, Issue #5).

Testet Laden (Repo→Score), Filtern und Sortieren – ohne Streamlit, gegen eine
temporäre SQLite-DB.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from flipit.core.config import settings
from flipit.processing import CarDetail, ListingRepository, RiskScorer, ScoringConfig
from flipit.ui.data import (
    SORT_OPTIONS,
    filter_listings,
    load_scored_listings,
    sort_listings,
)

SCORER = RiskScorer(ScoringConfig(reference_year=2025))


@pytest.fixture
def repo(tmp_path: Path) -> ListingRepository:
    cfg = replace(settings, db_path=tmp_path / "ui.db")
    repo = ListingRepository(config=cfg)
    repo.save(CarDetail(id="a", url="u/a", title="Audi A3", price=6000,
                        mileage=80_000, year=2020, description="Scheckheft gepflegt"))
    repo.save(CarDetail(id="b", url="u/b", title="BMW 3er", price=8000,
                        mileage=220_000, year=2010, description="Bastler, Motorschaden"))
    repo.save(CarDetail(id="c", url="u/c", title="VW Golf", price=7000,
                        mileage=150_000, year=2015, description=""))
    return repo


def test_load_scores_every_listing(repo: ListingRepository) -> None:
    items = load_scored_listings(repo, SCORER)
    assert len(items) == 3
    assert all(0 <= i.total <= 100 for i in items)


def test_filter_by_max_price(repo: ListingRepository) -> None:
    items = load_scored_listings(repo, SCORER)
    filtered = filter_listings(items, max_price=7000)
    assert {i.car.id for i in filtered} == {"a", "c"}


def test_filter_by_min_score(repo: ListingRepository) -> None:
    items = load_scored_listings(repo, SCORER)
    good = filter_listings(items, min_score=50)
    # Der gepflegte Audi (niedrige km, jung) muss übrig bleiben, der Bastler-BMW nicht.
    ids = {i.car.id for i in good}
    assert "a" in ids
    assert "b" not in ids


def test_filter_by_search(repo: ListingRepository) -> None:
    items = load_scored_listings(repo, SCORER)
    assert {i.car.id for i in filter_listings(items, search="golf")} == {"c"}


def test_sort_by_score_descending(repo: ListingRepository) -> None:
    items = sort_listings(load_scored_listings(repo, SCORER), "Score (hoch→niedrig)")
    totals = [i.total for i in items]
    assert totals == sorted(totals, reverse=True)
    assert items[0].car.id == "a"  # bestes Inserat zuerst


def test_sort_by_price_ascending(repo: ListingRepository) -> None:
    items = sort_listings(load_scored_listings(repo, SCORER), "Preis (niedrig→hoch)")
    prices = [i.car.price for i in items]
    assert prices == [6000, 7000, 8000]


def test_sort_options_are_valid(repo: ListingRepository) -> None:
    items = load_scored_listings(repo, SCORER)
    for key in SORT_OPTIONS:
        assert len(sort_listings(items, key)) == len(items)
