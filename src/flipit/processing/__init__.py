"""Processing-Modul: Datenextraktion, Bild-Download und Persistenz (MVP-3, Issue #3)."""

from flipit.processing.extract import ExtractionError, parse_detail
from flipit.processing.images import download_images
from flipit.processing.models import CarDetail
from flipit.processing.pipeline import process_detail_html, run
from flipit.processing.scoring import (
    FactorScore,
    RiskScorer,
    ScoreResult,
    ScoringConfig,
)
from flipit.processing.storage import ListingRepository

__all__ = [
    "CarDetail",
    "ExtractionError",
    "FactorScore",
    "ListingRepository",
    "RiskScorer",
    "ScoreResult",
    "ScoringConfig",
    "download_images",
    "parse_detail",
    "process_detail_html",
    "run",
]
