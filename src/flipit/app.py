"""Streamlit-Entrypoint für das Flipit-Dashboard.

Minimaler "Hello Flipit"-Einstiegspunkt (MVP-1). Wird in MVP-5 (Issue #5) zur
Inserate- und Score-Visualisierung ausgebaut.
"""

from __future__ import annotations

import streamlit as st

from flipit import __version__
from flipit.core.config import settings


def main() -> None:
    st.set_page_config(page_title=settings.app_title, page_icon="🚗", layout="wide")

    st.title(f"🚗 {settings.app_title}")
    st.caption(f"Kfz-Analyse-Tool für den österreichischen Fahrzeugmarkt · v{__version__}")

    st.success("Hello Flipit – das Fundament steht. Container läuft. ✅")

    st.markdown(
        """
        **Status:** MVP-1 (Docker & Streamlit Basis-Setup) abgeschlossen.

        Nächste Schritte laut MVP-Roadmap:
        - **#2** Willhaben Scraper – Basis-Logik
        - **#3** Datenextraktion & Persistenz
        - **#4** Risiko-Scoring Engine
        - **#5** Dashboard-Ausbau (Inserate & Score-Visualisierung)
        """
    )

    with st.sidebar:
        st.header("Konfiguration")
        st.write("Daten-Verzeichnis:", f"`{settings.data_dir}`")
        st.write("Bild-Verzeichnis:", f"`{settings.image_dir}`")


if __name__ == "__main__":
    main()
