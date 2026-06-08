# Änderungsprotokoll (Changelog)

Format orientiert an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Added
- **MVP-7: Marktwert-/Margen-Schätzung** (Issue #12)
  - `processing/valuation.py`: `MarketValuator` schätzt den Marktwert aus
    vergleichbaren Inseraten (Median, km-/Baujahr-Korridor) → `ValuationResult`
    (geschätzter Wert, Stichprobe, Marge absolut & prozentual).
  - Neuer **Margen-Faktor** im `RiskScorer` (`score(car, market_value=...)`),
    Default-Gewichte rebalanciert; `ScoringConfig` um Margen-Schwellen erweitert.
  - Dashboard zeigt Marktwert + Marge in Übersicht und Detail; Faktor im
    Score-Breakdown sichtbar.
  - Konfigurierbar via `.env` (`VALUATION_*`, `SCORE_WEIGHT_MARGIN`,
    `SCORE_MARGIN_*`); deterministische Offline-Tests (57 Tests gesamt grün).
- **MVP-5: Streamlit Dashboard – Inserate & Score-Visualisierung** (Issue #5)
  - `ui/data.py`: testbare Datenschicht (`load_scored_listings`, `filter_listings`,
    `sort_listings`) – verbindet Persistenz (MVP-3) mit Scoring (MVP-4).
  - `ui/dashboard.py`: Inserate-Übersicht (Tabelle mit Score-Balken),
    Detailansicht mit Metadaten/Bild und nachvollziehbarer Score-Zusammensetzung
    (Balkendiagramm + Breakdown-Tabelle der gewichteten Faktor-Beiträge).
  - `app.py`: ausgebautes Dashboard mit Sidebar (Scrape-Button, Filter,
    Sortierung) und Empty-State; löst „Hello Flipit" ab.
  - Modernisiert `use_container_width` → `width="stretch"`; 7 neue Tests
    (45 gesamt grün); verifiziert via Streamlit `AppTest` und im Docker-Container.
- **MVP-4: Risiko-Scoring Engine** (Issue #4)
  - `processing/scoring.py`: `RiskScorer` berechnet einen Gesamt-Score (0–100)
    plus transparenten `FactorScore`-Breakdown aus vier Faktoren (Preis/Marge,
    Kilometerstand, Alter, Beschreibungs-Signale).
  - `ScoringConfig` (env-getrieben via `from_env()`): konfigurierbare Gewichte,
    Schwellen und Schlagwort-Listen – nicht hardcoded.
  - Fehlende Felder werden neutral bewertet; `ScoreResult.explain()` für die UI.
  - 16 deterministische Unit-Tests (38 Tests gesamt grün).
- **MVP-3: Datenextraktion & Persistenz** (Issue #3)
  - `processing/models.py`: `CarDetail`-Dataclass mit allen Metadaten (Preis, km,
    Baujahr, Leistung kW/PS, Kraftstoff, Getriebe, Hubraum, Beschreibung, Bilder).
  - `processing/extract.py`: `parse_detail()` extrahiert die Detailseite aus dem
    `__NEXT_DATA__`-JSON; HTML-Beschreibung wird via BeautifulSoup bereinigt.
  - `processing/images.py`: `download_images()` lädt Bilder lokal (Pfad via `.env`),
    idempotent.
  - `processing/storage.py`: `ListingRepository` persistiert in **SQLite**
    (Upsert über `id`, wiederladbar nach Neustart).
  - `processing/pipeline.py`: `process_detail_html()` + `run()` (suchen → Detail →
    extrahieren → Bilder → persistieren).
  - Neue Config `DB_PATH`; Offline-Tests inkl. Detail-Fixture (23 Tests gesamt).
- **MVP-2: Willhaben Scraper – Basis-Logik** (Issue #2)
  - `scraper/willhaben.py`: `WillhabenScraper` mit Such-URL-Aufbau, HTTP-Abruf
    (requests, Timeout, freundliche Header, Fehlerbehandlung) und Parsing des
    `__NEXT_DATA__`-JSON zu `Listing`-Objekten.
  - `scraper/models.py`: `Listing`-Dataclass für Inserats-Basisdaten.
  - Konfigurierbare Suchparameter via `.env` (`SEARCH_MODELS`, `PRICE_MIN`/`MAX`,
    `REQUEST_DELAY`, `REQUEST_TIMEOUT`, `USER_AGENT`, `WILLHABEN_BASE_URL`).
  - `search_all()` mit Rate-Limiting und ID-Deduplizierung über mehrere Modelle.
  - Offline-Tests (`tests/`) gegen HTML-Fixture; `requirements-dev.txt` (pytest).
- **MVP-1: Docker & Streamlit Basis-Setup** (Issue #1)
  - Modulare Projektstruktur unter `src/flipit/` (`core`, `scraper`, `processing`, `ui`).
  - Env-getriebene Konfiguration (`core/config.py`) inkl. `.env.example`.
  - `Dockerfile` (python:3.12-slim) und `docker-compose.yml` (Service `web`, Port 8501).
  - Minimales "Hello Flipit"-Streamlit-Dashboard als Einstiegspunkt.
  - `.gitignore` / `.dockerignore` und persistentes `data/`-Verzeichnis.
