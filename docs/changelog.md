# Änderungsprotokoll (Changelog)

Format orientiert an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Added
- **MVP-1: Docker & Streamlit Basis-Setup** (Issue #1)
  - Modulare Projektstruktur unter `src/flipit/` (`core`, `scraper`, `processing`, `ui`).
  - Env-getriebene Konfiguration (`core/config.py`) inkl. `.env.example`.
  - `Dockerfile` (python:3.12-slim) und `docker-compose.yml` (Service `web`, Port 8501).
  - Minimales "Hello Flipit"-Streamlit-Dashboard als Einstiegspunkt.
  - `.gitignore` / `.dockerignore` und persistentes `data/`-Verzeichnis.
