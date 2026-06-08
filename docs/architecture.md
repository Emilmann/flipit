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
├── processing/   # Detail-Extraktion, Bild-Download, Persistenz (MVP-3, Issue #3); Bildanalyse (MVP-4)
└── ui/           # Wiederverwendbare Streamlit-Komponenten    (MVP-5, Issue #5)
```

### core/config.py
Lädt `.env` via `python-dotenv` und stellt eine `Settings`-Instanz (`settings`)
bereit (`app_title`, `data_dir`, `image_dir`, `db_path` sowie die Scraper-Parameter
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

### processing/ (MVP-3)
- **`models.py`** – `CarDetail`-Dataclass: vollständige Metadaten (Preis, km,
  Baujahr/-monat, Leistung in kW + abgeleitete PS, Kraftstoff, Getriebe, Hubraum,
  Beschreibung, Bild-URLs/-Pfade, Quell-URL).
- **`extract.py`** – `parse_detail()` liest `props.pageProps.advertDetails` aus dem
  `__NEXT_DATA__`-JSON der Detailseite; bereinigt die HTML-Beschreibung via
  BeautifulSoup. Reine, netzwerkfreie Funktion.
- **`images.py`** – `download_images()` lädt die Bilder nach
  `<image_dir>/<id>/<n>.jpg`, idempotent (vorhandene Dateien werden übersprungen).
- **`storage.py`** – `ListingRepository` persistiert `CarDetail` in **SQLite**
  (stdlib `sqlite3`, keine neue Abhängigkeit). Upsert über die Inserat-`id`;
  Spalten ohne Typ-Affinität bewahren int/str/None beim Roundtrip. Wiederladbar
  nach Neustart, abfragbar für das Dashboard (MVP-5).
- **`pipeline.py`** – `process_detail_html()` (offline testbar) und `run()`
  (vollständiger Lauf: suchen → Detail laden → extrahieren → Bilder → persistieren).

### processing/scoring.py (MVP-4)
Risiko-/Margen-Engine: `RiskScorer.score(car)` liefert ein `ScoreResult`
(Gesamt-Score 0–100 + `FactorScore`-Breakdown). Vier Faktoren – Preis (Marge zum
Budget), Kilometerstand, Alter und Beschreibungs-Signale (Schlagwörter) – werden
auf [0, 1] normalisiert (1 = beste Bewertung), gewichtet und aufsummiert.
Gewichte/Schwellen/Schlagwörter sind über `ScoringConfig` (env-getrieben,
`ScoringConfig.from_env()`) konfigurierbar. Fehlende Felder werden neutral (0.5)
bewertet. Reine, deterministische Logik; `ScoreResult.explain()` liefert eine
menschenlesbare Aufschlüsselung für das Dashboard (MVP-5). Seit MVP-7 enthält der
Breakdown zusätzlich einen **Margen-Faktor** (`score(car, market_value=...)`):
ohne Marktwert wird er neutral bewertet.

### processing/valuation.py (MVP-7)
`MarketValuator.estimate(car)` schätzt den Marktwert aus vergleichbaren Inseraten
desselben Modells (gleiche Marke+Modell, innerhalb km-/Baujahr-Toleranz) als
**Median** der Vergleichspreise und liefert ein `ValuationResult`
(geschätzter Wert, Stichprobengröße, absolute & prozentuale Marge). Bei zu wenigen
Vergleichswerten (`min_sample_size`) → `None` (neutrale Behandlung). Konfigurierbar
über `ValuationConfig` (env-getrieben). Der geschätzte Wert speist den
Margen-Faktor des `RiskScorer`.

### processing/image_analysis.py (MVP-6)
OpenCV-basierte, lokale Bildanalyse der heruntergeladenen Inseratsbilder.
`analyze_paths(paths)` berechnet je Bild Kennzahlen (Schärfe via Laplace-Varianz,
Helligkeit, Kontrast, Kantendichte) und aggregiert zu einem Bild-Score in [0, 1]
(`ImageAnalysisResult`). Der Score wird in der Pipeline berechnet, in
`CarDetail.image_score` persistiert und speist den `images`-Faktor des
`RiskScorer`. Konfigurierbar über `ImageAnalysisConfig` (env-getrieben).
**Abgrenzung:** bewusst ein grober Qualitäts-/Plausibilitäts-Proxy (z. B. können
unscharfe Fotos Mängel verschleiern), keine echte Schadenserkennung. Nutzt
`opencv-python-headless` (kein GUI im Container). Die SQLite-Persistenz ergänzt
fehlende Spalten automatisch (leichte Migration in `ListingRepository`).

### ui/ & app.py (MVP-5)
Das Streamlit-Dashboard verbindet persistierte Inserate (MVP-3) mit den Scores
(MVP-4):
- **`ui/data.py`** – reine, testbare Datenschicht: `load_scored_listings()`
  (Repo → Score), `filter_listings()` (Preis/Score/Titel) und `sort_listings()`
  (`SORT_OPTIONS`). `ScoredListing` bündelt `CarDetail` + `ScoreResult`.
- **`ui/dashboard.py`** – Streamlit-Komponenten: Inserate-Übersicht (Tabelle mit
  Score-Fortschrittsbalken), Detailansicht mit Metadaten/Bild und – als Kern der
  Nachvollziehbarkeit – ein Balkendiagramm + Tabelle der gewichteten
  Faktor-Beiträge.
- **`app.py`** – Entrypoint: Sidebar mit Scrape-Button, Filtern und Sortierung;
  Hauptbereich mit Übersicht und Detailauswahl. Graceful Empty-State, wenn die DB
  leer ist.

### Tests
`tests/` läuft offline gegen gespeicherte HTML-Fixturen
(`fixtures/willhaben_search.html`, `fixtures/willhaben_detail.html`) bzw. gegen
gestubbte Sessions und temporäre SQLite-DBs – kein Live-Call. Ausführen:
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
