# Änderungsprotokoll (Changelog)

Format orientiert an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Added
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
