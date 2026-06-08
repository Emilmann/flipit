"""Bildanalyse der Inseratsbilder via OpenCV (MVP-6, Issue #11).

Erste, bewusst einfache und **kostenlose, lokale** Evaluierung der Inseratsbilder.
Berechnet je Bild OpenCV-Kennzahlen (Schärfe, Helligkeit, Kontrast, Kantendichte)
und aggregiert sie zu einem Bild-Score in [0, 1] (1 = beste Bewertung), der als
Faktor in das Risiko-Scoring (MVP-4) einfließt.

Hinweis / Abgrenzung: Dies ist **keine** echte Schadenserkennung, sondern ein
grober Qualitäts-/Plausibilitäts-Proxy (z. B. unscharfe/zu dunkle Fotos können
Mängel verschleiern). Ein präziseres (ggf. ML-basiertes) Verfahren kann später
folgen.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ImageAnalysisConfig:
    """Schwellen für die Aggregation der Bild-Kennzahlen (env-getrieben)."""

    # Schärfe (Varianz des Laplace-Operators): worst → 0.0, best → 1.0
    sharpness_worst: float = 50.0
    sharpness_best: float = 500.0
    # Helligkeit (mittlerer Grauwert 0–255): ideal ~Mitte, Extreme = schlecht
    brightness_ideal: float = 128.0
    brightness_span: float = 110.0  # zulässige Abweichung bis Score 0

    @classmethod
    def from_env(cls) -> "ImageAnalysisConfig":
        return cls(
            sharpness_worst=_env_float("IMG_SHARPNESS_WORST", 50.0),
            sharpness_best=_env_float("IMG_SHARPNESS_BEST", 500.0),
            brightness_ideal=_env_float("IMG_BRIGHTNESS_IDEAL", 128.0),
            brightness_span=_env_float("IMG_BRIGHTNESS_SPAN", 110.0),
        )


@dataclass(frozen=True)
class ImageMetrics:
    """Rohe OpenCV-Kennzahlen eines einzelnen Bildes."""

    sharpness: float    # Varianz des Laplace-Operators
    brightness: float   # mittlerer Grauwert (0–255)
    contrast: float     # Standardabweichung der Grauwerte
    edge_density: float  # Anteil Kantenpixel (Canny), 0–1


@dataclass(frozen=True)
class ImageAnalysisResult:
    """Aggregiertes Ergebnis der Bildanalyse eines Inserats."""

    image_score: float          # Gesamt-Bild-Score 0–1 (1 = beste Bewertung)
    images_analyzed: int        # Anzahl erfolgreich analysierter Bilder
    avg_sharpness: float
    avg_brightness: float


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_metrics(image: np.ndarray) -> ImageMetrics:
    """Berechnet die OpenCV-Kennzahlen für ein bereits geladenes (BGR-)Bild."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float((edges > 0).mean())
    return ImageMetrics(
        sharpness=sharpness,
        brightness=brightness,
        contrast=contrast,
        edge_density=edge_density,
    )


def analyze_image(path: str | Path) -> ImageMetrics | None:
    """Lädt ein Bild von der Platte und berechnet seine Kennzahlen."""
    image = cv2.imread(str(path))
    if image is None:
        logger.warning("Bild nicht lesbar: %s", path)
        return None
    return compute_metrics(image)


def _quality_from_metrics(m: ImageMetrics, config: ImageAnalysisConfig) -> float:
    """Bildet die Kennzahlen eines Bildes auf einen Qualitäts-Score [0, 1] ab."""
    sharp = _clamp(
        (m.sharpness - config.sharpness_worst)
        / (config.sharpness_best - config.sharpness_worst)
    )
    brightness_dev = abs(m.brightness - config.brightness_ideal)
    bright = _clamp(1.0 - brightness_dev / config.brightness_span)
    # Schärfe doppelt gewichtet (wichtigster Plausibilitäts-Indikator).
    return _clamp((2 * sharp + bright) / 3)


def analyze_paths(
    paths: list[str],
    config: ImageAnalysisConfig | None = None,
) -> ImageAnalysisResult | None:
    """Analysiert mehrere Bildpfade und aggregiert zu einem Bild-Score.

    Liefert `None`, wenn kein Bild lesbar ist (neutrale Behandlung im Scoring).
    """
    config = config or ImageAnalysisConfig()
    metrics = [m for m in (analyze_image(p) for p in paths) if m is not None]
    if not metrics:
        return None

    qualities = [_quality_from_metrics(m, config) for m in metrics]
    return ImageAnalysisResult(
        image_score=round(sum(qualities) / len(qualities), 4),
        images_analyzed=len(metrics),
        avg_sharpness=round(sum(m.sharpness for m in metrics) / len(metrics), 1),
        avg_brightness=round(sum(m.brightness for m in metrics) / len(metrics), 1),
    )
