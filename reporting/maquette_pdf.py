"""Génération PDF du rapport maquette via Playwright (vue HTML Chart.js)."""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def write_maquette_pdf_to_path(url: str, out_path: Path) -> None:
    """Charge l’URL (serveur Flask joignable) et écrit un PDF A4 unique à `out_path`."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright n’est pas installé. Exécutez : pip install playwright && playwright install chromium"
        ) from e

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 1600})
        try:
            page.goto(url, wait_until="networkidle", timeout=180000)
            page.wait_for_timeout(4500)
            page.emulate_media(media="screen")
            page.pdf(
                path=str(out_path),
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            browser.close()

    _log.info("PDF maquette écrit : %s", out_path)
