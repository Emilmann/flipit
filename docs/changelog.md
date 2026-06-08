# Änderungsprotokoll (Changelog)

Format orientiert an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Added
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
