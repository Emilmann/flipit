"""Einstiegspunkt für den GitHub Actions Auto-Scraper.

Wird von .github/workflows/scrape.yml aufgerufen. Setzt PYTHONPATH auf src/,
damit `import flipit` ohne Installation funktioniert. Image-Download ist
deaktiviert (kein persistenter Storage in CI).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flipit.processing.pipeline import run

if __name__ == "__main__":
    run(download=False)
