# Projekt-Spezifikation (Project Spec): Flipit

## 1. Produktanforderungen (Product Requirements)
**Zielgruppe:** - Interner Gebrauch für Kfz-Analyse und schnelles Bewerten von Inseraten auf dem österreichischen Markt.

**Problemstellung:** - Manuelle Filterung von Schnäppchen auf willhaben.at ist zeitintensiv.
- Risiko- und Margenkalkulationen müssen präzise auf ein Gesamtbudget von 6.000€ bis 8.000€ abgestimmt sein.

**Kernfunktionen:** - **Scraping:** Automatisierte Abfrage von willhaben.at nach vordefinierten Fahrzeugmodellen.
- **Datenextraktion:** Auslesen von Metadaten (Kilometerstand, Preis, Baujahr, Leitung, Inseratbeschreibung) sowie Download von Bildmaterial.
- **Feineinstellung (Scoring):** Eine Benutzeroberfläche zur Darstellung der Riskobewertung um zu sehen wie diese gehändet wird.
- **Bildanalyse:** Erste kostenlose Evaluierung von Karosserieschäden via OpenCV/lokalen Algorithmen.

**Benutzerinteraktion & UX:** - Eine übersichtliche Web-Oberfläche (Streamlit Dashboard) zur Anzeige von Inseraten, berechneten Scores und zur nachvollziebaren klaren darstellung wie die Gewichtungen zusammenkommt.

**Meilensteine & MVP:** - **MVP:** Lokale Docker-Struktur auf dem PC. Scraping von Basisdaten, Berechnung eines Risiko-Scores und Darstellung in der Webapp.

## 2. Technische Anforderungen (Engineering Design)
**Tech Stack:** - **Backend/Scraper:** Python (BeautifulSoup/Selenium/Requests)
- **Frontend/Dashboard:** Streamlit (Python-basiert)
- **Bildverarbeitung:** OpenCV (kostenlos, lokal ausführbar)
- **Infrastruktur:** Docker & Docker-Compose (Entwicklung lokal, Deployment auf Raspberry Pi)
