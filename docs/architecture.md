# Architektur: Flipit

## Überblick
Flipit ist ein lokal unter Docker laufendes Analyse-Tool für den österreichischen
Fahrzeugmarkt. Die Anwendung ist modular aufgebaut, mit klarer Trennung zwischen
Scraping, Datenverarbeitung und UI (vgl. `claude.md`).

## Modulstruktur
```
src/flipit/
├── app.py        # Streamlit-Entrypoint (Dashboard)
├── core/         # Zentrale Konfiguration (env-getrieben) & gemeinsame Utilities
├── scraper/      # Abfrage & Parsing von willhaben.at        (MVP-2, Issue #2)
├── processing/   # Datenextraktion, Persistenz, Bildanalyse  (MVP-3/4, Issues #3/#4)
└── ui/           # Wiederverwendbare Streamlit-Komponenten    (MVP-5, Issue #5)
```

### core/config.py
Lädt `.env` via `python-dotenv` und stellt eine `Settings`-Instanz (`settings`)
bereit (`app_title`, `data_dir`, `image_dir`). Alle Module sollen Konfiguration von
hier beziehen — keine Hardcoded-Pfade.

## Container-Aufbau (MVP-1)
- **Base-Image:** `python:3.12-slim`
- **Service `web`** (docker-compose): startet Streamlit auf Port `8501`.
- **Bind-Mounts:** `./src` (Live-Reload) und `./data` (persistente Daten/Bilder).
- **Konfiguration:** über `.env` (Vorlage: `.env.example`).

## Befehle
- Start: `docker-compose up --build`
- Stopp: `docker-compose down`
- Dashboard: http://localhost:8501

## Roadmap (MVP)
Fundament (#1) → Scraper (#2) → Datenextraktion/Persistenz (#3) →
Risiko-Scoring (#4) → Dashboard-Ausbau (#5).
