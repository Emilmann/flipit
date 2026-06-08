"""Tests der OpenCV-Bildanalyse (MVP-6, Issue #11).

Erzeugt synthetische Bilder zur Laufzeit (kein Binär-Fixture nötig) und prüft
Kennzahlen sowie Aggregation deterministisch und offline.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from flipit.processing import analyze_image, analyze_paths
from flipit.processing.image_analysis import ImageAnalysisConfig, compute_metrics


def _sharp_image() -> np.ndarray:
    """Scharfes Bild mit vielen Kanten (Schachbrettmuster)."""
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    tile = 10
    for y in range(0, 120, tile):
        for x in range(0, 120, tile):
            if (x // tile + y // tile) % 2 == 0:
                img[y:y + tile, x:x + tile] = 255
    return img


def _blurry_image() -> np.ndarray:
    return cv2.GaussianBlur(_sharp_image(), (21, 21), 0)


def _write(path: Path, img: np.ndarray) -> str:
    cv2.imwrite(str(path), img)
    return str(path)


def test_compute_metrics_fields() -> None:
    m = compute_metrics(_sharp_image())
    assert m.sharpness > 0
    assert 0 <= m.brightness <= 255
    assert 0 <= m.edge_density <= 1


def test_sharp_has_higher_sharpness_than_blurry() -> None:
    assert compute_metrics(_sharp_image()).sharpness > compute_metrics(_blurry_image()).sharpness


def test_analyze_image_reads_file(tmp_path: Path) -> None:
    path = _write(tmp_path / "sharp.jpg", _sharp_image())
    metrics = analyze_image(path)
    assert metrics is not None
    assert metrics.sharpness > 0


def test_analyze_image_returns_none_for_missing(tmp_path: Path) -> None:
    assert analyze_image(tmp_path / "does_not_exist.jpg") is None


def test_analyze_paths_aggregates(tmp_path: Path) -> None:
    paths = [
        _write(tmp_path / "a.png", _sharp_image()),
        _write(tmp_path / "b.png", _sharp_image()),
    ]
    result = analyze_paths(paths)
    assert result is not None
    assert result.images_analyzed == 2
    assert 0.0 <= result.image_score <= 1.0


def test_sharp_scores_higher_than_blurry(tmp_path: Path) -> None:
    sharp = analyze_paths([_write(tmp_path / "s.png", _sharp_image())])
    blurry = analyze_paths([_write(tmp_path / "b.png", _blurry_image())])
    assert sharp is not None and blurry is not None
    assert sharp.image_score > blurry.image_score


def test_analyze_paths_none_when_unreadable(tmp_path: Path) -> None:
    (tmp_path / "broken.jpg").write_text("not an image")
    assert analyze_paths([str(tmp_path / "broken.jpg")]) is None


def test_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("IMG_SHARPNESS_BEST", "800")
    cfg = ImageAnalysisConfig.from_env()
    assert cfg.sharpness_best == 800.0


def test_pipeline_sets_image_score(tmp_path: Path) -> None:
    """process_detail_html lädt Bilder (gestubbt) und berechnet den Bild-Score."""
    from dataclasses import replace

    from flipit.core.config import settings
    from flipit.processing import ListingRepository, process_detail_html

    detail = (Path(__file__).parent / "fixtures" / "willhaben_detail.html").read_text(
        encoding="utf-8"
    )
    cfg = replace(settings, db_path=tmp_path / "db.sqlite", image_dir=tmp_path / "img")
    repo = ListingRepository(config=cfg)

    image_bytes = cv2.imencode(".jpg", _sharp_image())[1].tobytes()

    class _Resp:
        content = image_bytes

        def raise_for_status(self) -> None:
            return None

    class _Session:
        def get(self, url: str, timeout: int = 0) -> "_Resp":
            return _Resp()

    car = process_detail_html(
        detail, "https://willhaben.at/x", repo=repo, config=cfg,
        session=_Session(), download=True,
    )
    assert car.image_score is not None
    assert 0.0 <= car.image_score <= 1.0
    # Persistiert und wieder ladbar.
    assert repo.get(car.id).image_score == car.image_score
