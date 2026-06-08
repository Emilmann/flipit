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
bereit (`app_title`, `data_dir`, `image_dir` sowie die Scraper-Parameter
`search_models`, `price_min`/`price_max`, `willhaben_base_url`, `request_delay`,
`request_timeout`, `user_agent`). Alle Module sollen Konfiguration von hier
beziehen — keine Hardcoded-Werte.

### scraper/ (MVP-2)
- **`models.py`** – `Listing`-Dataclass: Basisdaten eines Inserats (id, title,
  url, price, year, mileage, make, model, location, postcode, seller).
- **`willhaben.py`** – `WillhabenScraper` fragt die willhaben-Gebrauchtwagensuche
  ab. willhaben ist eine Next.js-App; die Treffer stecken als JSON im
  `__NEXT_DATA__`-Script (`props.pageProps.searchResult.advertSummaryList.advertSummary[]`).
  Das Parsen dieses JSON (statt CSS-Selektoren) ist robust gegen Markup-Änderungen,
  daher reicht `requests` (kein Selenium). `parse_listings()` ist eine reine,
  netzwerkfreie Funktion → Grundlage der Offline-Tests. `search_all()` iteriert über
  die konfigurierten Modelle mit freundlichem Rate-Limiting (`request_delay`) und
  ID-Deduplizierung.

### Tests
`tests/` läuft offline gegen eine gespeicherte HTML-Fixture
(`tests/fixtures/willhaben_search.html`) – kein Live-Call. Ausführen:
`pip install -r requirements-dev.txt && pytest`.

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
