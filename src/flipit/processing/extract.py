"""Extraktion der Metadaten aus einer willhaben-Inserat-Detailseite (MVP-3).

Wie beim Scraper (MVP-2) liegen die Daten als JSON im `__NEXT_DATA__`-Script,
hier unter `props.pageProps.advertDetails`. `parse_detail()` ist eine reine,
netzwerkfreie Funktion und damit Grundlage der Offline-Tests.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from flipit.processing.models import CarDetail

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


class ExtractionError(RuntimeError):
    """Fehler beim Parsen einer Detailseite."""


def _extract_next_data(html: str) -> dict[str, Any]:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise ExtractionError("Kein __NEXT_DATA__-Script in der Detailseite gefunden.")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensiv
        raise ExtractionError(f"__NEXT_DATA__-JSON nicht parsebar: {exc}") from exc


def _attr_map(ad: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for attr in ad.get("attributes", {}).get("attribute", []):
        name = attr.get("name")
        values = attr.get("values")
        if name and values:
            result[name] = values[0]
    return result


def _to_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def _clean_html(raw: str | None) -> str:
    """Entfernt HTML-Tags aus dem Beschreibungstext und normalisiert Whitespace."""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _image_urls(ad: dict[str, Any]) -> list[str]:
    images = ad.get("advertImageList", {}).get("advertImage", [])
    urls = []
    for image in images:
        url = image.get("referenceImageUrl") or image.get("mainImageUrl")
        if url:
            urls.append(url)
    return urls


def parse_detail(html: str, source_url: str = "") -> CarDetail:
    """Extrahiert ein `CarDetail` aus dem HTML einer willhaben-Detailseite."""
    data = _extract_next_data(html)
    try:
        ad = data["props"]["pageProps"]["advertDetails"]
    except (KeyError, TypeError) as exc:
        raise ExtractionError("advertDetails nicht im erwarteten Pfad gefunden.") from exc

    attrs = _attr_map(ad)
    is_private_raw = attrs.get("ISPRIVATE")

    return CarDetail(
        id=str(ad.get("id", "")),
        url=source_url,
        title=attrs.get("HEADING") or ad.get("description") or "",
        make=attrs.get("CAR_MODEL/MAKE"),
        model=attrs.get("CAR_MODEL/MODEL"),
        model_spec=attrs.get("CAR_MODEL/MODEL_SPECIFICATION"),
        price=_to_int(attrs.get("PRICE")),
        mileage=_to_int(attrs.get("MILEAGE")),
        year=_to_int(attrs.get("YEAR_MODEL")),
        month=_to_int(attrs.get("YEAR_MODEL_MONTH")),
        power_kw=_to_int(attrs.get("ENGINE/EFFECT")),
        fuel=attrs.get("ENGINE/FUEL"),
        transmission=attrs.get("TRANSMISSION"),
        engine_volume=_to_int(attrs.get("ENGINE/VOLUME")),
        car_type=attrs.get("CAR_TYPE"),
        color=attrs.get("EXTERIOR_COLOUR_MAIN"),
        owners=_to_int(attrs.get("NO_OF_OWNERS")),
        description=_clean_html(attrs.get("DESCRIPTION")),
        location=attrs.get("LOCATION/ADDRESS_2"),
        postcode=attrs.get("CONTACT/ADDRESS_POSTCODE"),
        seller=attrs.get("CONTACT/COMPANY"),
        is_private=(is_private_raw == "1") if is_private_raw is not None else None,
        image_urls=_image_urls(ad),
        scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
