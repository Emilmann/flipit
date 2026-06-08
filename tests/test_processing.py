"""Offline-Tests für Extraktion, Bild-Download und Persistenz (MVP-3, Issue #3).

Kein Live-Call: Detail-Parsing läuft gegen eine HTML-Fixture, Bild-Download und
Pipeline gegen eine gestubbte requests-Session.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from flipit.core.config import settings
from flipit.processing import (
    CarDetail,
    ExtractionError,
    ListingRepository,
    download_images,
    parse_detail,
    process_detail_html,
)

FIXTURE = Path(__file__).parent / "fixtures" / "willhaben_detail.html"
SOURCE_URL = "https://www.willhaben.at/iad/gebrauchtwagen/d/auto/audi-a3-1228790209/"


@pytest.fixture
def detail_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def car(detail_html: str) -> CarDetail:
    return parse_detail(detail_html, source_url=SOURCE_URL)


# --- Extraktion ---

def test_extracts_all_metadata(car: CarDetail) -> None:
    assert car.id == "1228790209"
    assert car.url == SOURCE_URL
    assert car.make == "Audi"
    assert car.model == "A3"
    assert car.price == 7450
    assert car.mileage == 225800
    assert car.year == 2014
    assert car.power_kw == 110
    assert car.fuel == "Diesel"
    assert car.transmission == "Automatik"
    assert car.engine_volume == 1968
    assert car.is_private is False


def test_power_ps_derived(car: CarDetail) -> None:
    assert car.power_ps == 150  # 110 kW ≈ 150 PS


def test_description_html_is_stripped(car: CarDetail) -> None:
    assert car.description
    assert "<" not in car.description and ">" not in car.description


def test_image_urls_extracted(car: CarDetail) -> None:
    assert len(car.image_urls) == 2
    assert all(url.startswith("https://") for url in car.image_urls)


def test_missing_next_data_raises() -> None:
    with pytest.raises(ExtractionError):
        parse_detail("<html><body>nichts</body></html>")


# --- Bild-Download (gestubbte Session) ---

class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, timeout: int = 0) -> _FakeResponse:
        self.calls.append(url)
        return _FakeResponse(b"\xff\xd8\xff fake-jpeg")


def test_download_images_writes_files(car: CarDetail, tmp_path: Path) -> None:
    cfg = replace(settings, image_dir=tmp_path / "images")
    session = _FakeSession()
    paths = download_images(car, config=cfg, session=session)  # type: ignore[arg-type]

    assert len(paths) == 2
    assert len(session.calls) == 2
    assert all(Path(p).exists() for p in paths)
    assert car.image_paths == paths
    assert all(car.id in p for p in paths)


def test_download_images_is_idempotent(car: CarDetail, tmp_path: Path) -> None:
    cfg = replace(settings, image_dir=tmp_path / "images")
    download_images(car, config=cfg, session=_FakeSession())  # type: ignore[arg-type]
    second = _FakeSession()
    download_images(car, config=cfg, session=second)  # type: ignore[arg-type]
    assert second.calls == []  # bereits vorhanden → kein erneuter Download


# --- Persistenz (temporäre SQLite-DB) ---

@pytest.fixture
def repo(tmp_path: Path) -> ListingRepository:
    cfg = replace(settings, db_path=tmp_path / "test.db")
    return ListingRepository(config=cfg)


def test_save_and_load_roundtrip(repo: ListingRepository, car: CarDetail) -> None:
    car.image_paths = ["/data/images/1228790209/1.jpg"]
    repo.save(car)
    loaded = repo.get(car.id)

    assert loaded is not None
    assert loaded.id == car.id
    assert loaded.price == 7450          # bleibt int
    assert loaded.mileage == 225800
    assert loaded.is_private is False    # bleibt bool
    assert loaded.image_paths == ["/data/images/1228790209/1.jpg"]
    assert loaded == car


def test_persists_across_new_repo_instance(
    tmp_path: Path, car: CarDetail
) -> None:
    cfg = replace(settings, db_path=tmp_path / "persist.db")
    ListingRepository(config=cfg).save(car)
    # Neue Instanz = "nach Neustart" – Daten müssen weiterhin ladbar sein.
    reloaded = ListingRepository(config=cfg).get(car.id)
    assert reloaded is not None
    assert reloaded.title == car.title


def test_upsert_dedupes_by_id(repo: ListingRepository, car: CarDetail) -> None:
    repo.save(car)
    repo.save(replace(car, price=6999))
    assert repo.count() == 1
    assert repo.get(car.id).price == 6999


def test_all_returns_sorted_by_price(repo: ListingRepository, car: CarDetail) -> None:
    repo.save(replace(car, id="b", price=8000))
    repo.save(replace(car, id="a", price=6000))
    prices = [c.price for c in repo.all()]
    assert prices == [6000, 8000]


# --- Pipeline (offline, ohne Download) ---

def test_pipeline_parses_and_persists(
    detail_html: str, repo: ListingRepository
) -> None:
    car = process_detail_html(
        detail_html, SOURCE_URL, repo=repo, download=False
    )
    assert car.id == "1228790209"
    assert repo.count() == 1
    assert repo.get(car.id).price == 7450
