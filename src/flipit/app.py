"""Streamlit-Entrypoint für das Flipit-Dashboard (MVP-5, Issue #5).

Funktionale Übersicht: listet persistierte Inserate (MVP-3) mit berechnetem
Risiko-Score (MVP-4), erlaubt Filtern/Sortieren und zeigt pro Inserat die
nachvollziehbare Score-Zusammensetzung.
"""

from __future__ import annotations

import streamlit as st

from flipit import __version__
from flipit.core.config import settings
from flipit.processing import ListingRepository, RiskScorer
from flipit.ui.dashboard import render_detail, render_overview
from flipit.ui.data import (
    SORT_OPTIONS,
    filter_listings,
    load_scored_listings,
    sort_listings,
)


def _trigger_scrape() -> None:
    """Stößt einen vollständigen Scrape-/Verarbeitungslauf an (Live-Netzwerk)."""
    from flipit.processing import run

    with st.spinner("Suche Inserate auf willhaben und verarbeite Details …"):
        try:
            cars = run(config=settings)
            st.success(f"{len(cars)} Inserate aktualisiert.")
        except Exception as exc:  # robuste UI – Fehler anzeigen, nicht crashen
            st.error(f"Lauf fehlgeschlagen: {exc}")


def main() -> None:
    st.set_page_config(page_title=settings.app_title, page_icon="🚗", layout="wide")
    st.title(f"🚗 {settings.app_title}")
    st.caption(f"Kfz-Analyse für den österreichischen Markt · v{__version__}")

    repo = ListingRepository(config=settings)
    scored = load_scored_listings(repo, RiskScorer())

    with st.sidebar:
        st.header("Steuerung")
        if st.button("🔄 Inserate aktualisieren (Scrape)", width="stretch"):
            _trigger_scrape()
            st.rerun()

        st.divider()
        st.subheader("Filter & Sortierung")
        sort_key = st.selectbox("Sortieren nach", SORT_OPTIONS)
        max_price = st.slider(
            "Maximaler Preis (€)",
            min_value=0,
            max_value=max(settings.price_max, 20000),
            value=max(settings.price_max, 20000),
            step=500,
        )
        min_score = st.slider("Mindest-Score", 0, 100, 0, step=5)
        search = st.text_input("Suche im Titel")

        st.divider()
        st.caption(f"Suchmodelle: {', '.join(settings.search_models)}")
        st.caption(f"Budget: € {settings.price_min:,} – € {settings.price_max:,}".replace(",", "."))

    if not scored:
        st.info(
            "Noch keine Inserate gespeichert. Starte links **Inserate aktualisieren** "
            "oder fülle die Datenbank über die Verarbeitungs-Pipeline."
        )
        return

    items = filter_listings(scored, max_price=max_price, min_score=min_score, search=search)
    items = sort_listings(items, sort_key)

    st.subheader(f"Inserate ({len(items)} von {len(scored)})")
    if not items:
        st.warning("Keine Inserate für die aktuellen Filter.")
        return
    render_overview(items)

    st.divider()
    labels = {f"{i.car.title[:60]}  ·  {i.total:.0f} Pkt": i for i in items}
    choice = st.selectbox("Detailansicht", list(labels.keys()))
    render_detail(labels[choice])


if __name__ == "__main__":
    main()
