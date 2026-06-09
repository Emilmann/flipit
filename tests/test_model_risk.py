"""Unit-Tests für ModelRiskLookup Forum-Recherche (MVP-9)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from flipit.processing.model_risk import ModelRiskLookup
from flipit.processing.models import CarDetail


def make_car(**kwargs) -> CarDetail:
    base = dict(
        id="1",
        url="https://example.test/1",
        make="VW",
        model="Golf",
        year=2015,
        mileage=150_000,
        fuel="Diesel",
    )
    base.update(kwargs)
    return CarDetail(**base)


def make_lookup(google_api_key: str = "key", google_cse_id: str = "cx") -> ModelRiskLookup:
    return ModelRiskLookup(
        db_path=":memory:",
        google_api_key=google_api_key,
        google_cse_id=google_cse_id,
    )


class TestFetchForumSnippets:
    def test_returns_empty_without_api_key(self) -> None:
        lu = make_lookup(google_api_key="")
        result = lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
        assert result == []

    def test_returns_empty_without_cse_id(self) -> None:
        lu = make_lookup(google_cse_id="")
        result = lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
        assert result == []

    def test_no_http_request_without_credentials(self) -> None:
        lu = make_lookup(google_api_key="", google_cse_id="")
        with patch("flipit.processing.model_risk.requests.get") as mock_get:
            lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
            mock_get.assert_not_called()

    def test_returns_empty_on_request_error(self) -> None:
        lu = make_lookup()
        with patch("flipit.processing.model_risk.requests.get") as mock_get:
            mock_get.side_effect = Exception("connection refused")
            result = lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
        assert result == []

    def test_returns_empty_on_http_error(self) -> None:
        lu = make_lookup()
        with patch("flipit.processing.model_risk.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")
            mock_get.return_value = mock_resp
            result = lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
        assert result == []

    def test_parses_title_and_snippet(self) -> None:
        lu = make_lookup()
        api_response = {
            "items": [
                {"title": "VW Golf Steuerkette", "snippet": "Bekanntes Problem ab 2013..."},
                {"title": "Golf Rost Erfahrung", "snippet": "Schwellerrost häufig..."},
            ]
        }
        with patch("flipit.processing.model_risk.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = api_response
            mock_get.return_value = mock_resp
            result = lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
        assert len(result) == 2
        assert result[0]["title"] == "VW Golf Steuerkette"
        assert result[1]["snippet"] == "Schwellerrost häufig..."

    def test_returns_empty_list_when_no_items(self) -> None:
        lu = make_lookup()
        with patch("flipit.processing.model_risk.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {}
            mock_get.return_value = mock_resp
            result = lu._fetch_forum_snippets("VW", "Golf", 2015, "Diesel")
        assert result == []


class TestFormatForumSnippets:
    def test_empty_returns_fallback(self) -> None:
        text = ModelRiskLookup._format_forum_snippets([])
        assert "Keine" in text

    def test_formats_title_and_snippet(self) -> None:
        snippets = [{"title": "Golf Mängel", "snippet": "Steuerkette verschlissen"}]
        text = ModelRiskLookup._format_forum_snippets(snippets)
        assert "Golf Mängel" in text
        assert "Steuerkette" in text

    def test_trims_to_five(self) -> None:
        snippets = [{"title": f"Titel {i}", "snippet": f"Text {i}"} for i in range(8)]
        text = ModelRiskLookup._format_forum_snippets(snippets)
        assert "... und 3 weitere" in text
        assert text.count("- Titel") == 5

    def test_no_overflow_marker_for_exactly_five(self) -> None:
        snippets = [{"title": f"T{i}", "snippet": f"S{i}"} for i in range(5)]
        text = ModelRiskLookup._format_forum_snippets(snippets)
        assert "weitere" not in text
