# Claude Code Kontext: Flipit

## Projektübersicht
Flipit ist ein Docker-basiertes Analyse-Tool für den Fahrzeugmarkt. Es durchsucht Inserate, bewertet Risiken algorithmisch und stellt die Ergebnisse in einem Streamlit-Dashboard dar.

## Entwicklungs-Richtlinien
- **Umgebung:** Aktuell reine lokale Entwicklung auf dem PC unter Docker. Späteres Ziel: Raspberry Pi.
- **Code-Stil:** Modularer Python-Code. Trennung zwischen Scraper-Logik, Datenverarbeitung (OpenCV) und UI (Streamlit).
- **Sicherheit:** `.env`-Dateien für Pfade oder potenzielle Logins nutzen. Keine Hardcoded-Konfigurationen im Code.

## Wichtige Befehle (Local Docker)
- **Container starten:** `docker-compose up --build`
- **Container stoppen:** `docker-compose down`

## Repository-Etikette & GitHub (via MCP)
- **GitHub MCP-Server:** Dieses Projekt ist mit einem Remote-Repository auf GitHub verknüpft und du (Claude) hast über den GitHub MCP-Server direkten API-Zugriff darauf.
- **Issue-based Development:** Bitte nutze den MCP-Server proaktiv! Wenn wir neue Funktionen oder Bugfixes besprechen, frage mich, ob du dafür ein GitHub Issue erstellen sollst, oder lies bestehende Issues aus, bevor du mit der Arbeit beginnst.
- **Commits & PRs:** Erstelle nach logischen Meilensteinen (z.B. wenn ein Docker-Container erfolgreich läuft) selbstständig saubere Git-Commits. Wenn wir größere Features (wie Meilensteine aus der `project_spec.md`) abschließen, pushe die Änderungen über den MCP-Server oder lokal als Push auf den Remote-Branch.

## Referenzierte Dokumente (Automated Documentation)
*Bitte konsultiere diese Dateien im Ordner `docs/` für tiefere Details und halte sie stets aktuell:*
- Spezifikation: `docs/project_spec.md`
- Architektur: `docs/architecture.md`
- Änderungsprotokoll: `docs/changelog.md`
