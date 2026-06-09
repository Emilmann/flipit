"""Streamlit-Darstellung des Dashboards (MVP-5, Issue #5).

Rendert Inserate-Übersicht, Detailansicht und die nachvollziehbare
Score-Zusammensetzung. Die testbare Datenlogik liegt in `ui/data.py`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from flipit.ui.data import ScoredListing


def _fmt_price(value: int | None) -> str:
    return f"€ {value:,.0f}".replace(",", ".") if value is not None else "–"


def _fmt_margin(item: ScoredListing) -> str:
    if not item.valuation or item.valuation.margin is None:
        return "–"
    sign = "+" if item.valuation.margin >= 0 else "−"
    return f"{sign}{_fmt_price(abs(item.valuation.margin))}"


def render_overview(items: list[ScoredListing]) -> None:
    """Tabellarische Übersicht der Inserate mit Kernmetadaten + Score."""
    rows = [
        {
            "Score": round(i.total, 1),
            "Titel": i.car.title,
            "Preis": _fmt_price(i.car.price),
            "Marktwert": _fmt_price(i.valuation.estimated_value) if i.valuation else "–",
            "Marge": _fmt_margin(i),
            "km": i.car.mileage,
            "Baujahr": i.car.year,
            "Ort": i.car.location or "–",
        }
        for i in items
    ]
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"
            )
        },
    )


def render_weight_chart(scored: ScoredListing) -> None:
    """Balkendiagramm der gewichteten Beiträge je Faktor (Score-Zusammensetzung)."""
    df = pd.DataFrame(
        {
            "Faktor": [f.name for f in scored.score.factors],
            "Beitrag": [round(f.contribution * 100, 1) for f in scored.score.factors],
        }
    ).set_index("Faktor")
    st.bar_chart(df, horizontal=True)


def render_breakdown_table(scored: ScoredListing) -> None:
    """Detaillierte, nachvollziehbare Aufschlüsselung der Faktoren."""
    rows = [
        {
            "Faktor": f.name,
            "Rohwert": str(f.raw_value),
            "Normalisiert": f"{f.normalized:.2f}",
            "Gewicht": f"{f.weight:.2f}",
            "Beitrag (Punkte)": round(f.contribution * 100, 1),
        }
        for f in scored.score.factors
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_detail(scored: ScoredListing) -> None:
    """Detailansicht eines Inserats inkl. Score-Breakdown."""
    car = scored.car
    st.subheader(car.title or f"Inserat {car.id}")

    col_img, col_meta = st.columns([1, 2])
    with col_img:
        local = car.image_paths[0] if car.image_paths and Path(car.image_paths[0]).exists() else None
        first_image = local or (car.image_urls[0] if car.image_urls else None)
        if first_image:
            st.image(first_image, width="stretch")
        else:
            st.info("Kein Bild verfügbar.")

    with col_meta:
        st.metric("Gesamt-Score", f"{scored.total:.1f} / 100")
        c1, c2, c3 = st.columns(3)
        c1.metric("Preis", _fmt_price(car.price))
        c2.metric("Kilometerstand", f"{car.mileage:,.0f} km".replace(",", ".") if car.mileage else "–")
        c3.metric("Baujahr", car.year or "–")
        c4, c5, c6 = st.columns(3)
        c4.metric("Leistung", f"{car.power_ps} PS" if car.power_ps else "–")
        c5.metric("Kraftstoff", car.fuel or "–")
        c6.metric(
            "Bildqualität",
            f"{car.image_score * 100:.0f} %" if car.image_score is not None else "–",
            help="OpenCV-Bildanalyse (MVP-6): grober Qualitäts-/Plausibilitäts-Proxy.",
        )

    if scored.valuation:
        val = scored.valuation
        st.markdown("#### Marktwert-Schätzung")
        m1, m2, m3 = st.columns(3)
        m1.metric("Geschätzter Marktwert", _fmt_price(val.estimated_value))
        if val.margin is not None:
            m2.metric(
                "Marge",
                _fmt_margin(scored),
                delta=f"{val.margin_pct * 100:+.0f}%" if val.margin_pct is not None else None,
            )
        m3.metric("Vergleichsinserate", val.sample_size)
        st.caption(
            "Marktwert = Median vergleichbarer Inserate (gleiches Modell, ähnlicher "
            "km-Stand & Baujahr). Marge = Marktwert − Kaufpreis."
        )
    else:
        st.info("Zu wenige Vergleichsinserate für eine Marktwert-Schätzung.")

    st.markdown("#### Score-Zusammensetzung")
    st.caption("So setzt sich der Gesamt-Score aus den gewichteten Faktoren zusammen:")
    render_weight_chart(scored)
    render_breakdown_table(scored)

    if car.model_risk_notes:
        with st.expander("🔍 Modell-Risiko Bewertung (Gemini)"):
            score_pct = f"{car.model_risk_score * 100:.0f} %" if car.model_risk_score is not None else "–"
            st.caption(f"Modell-Risiko Score: {score_pct} (100 % = geringstes Risiko)")
            st.write(car.model_risk_notes)

    if car.description:
        with st.expander("Beschreibung"):
            st.write(car.description)
    if car.url:
        st.link_button("Auf willhaben öffnen ↗", car.url)
