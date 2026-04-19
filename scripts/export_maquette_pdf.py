#!/usr/bin/env python3
"""
CLI optionnel : exporte vers static/exports/rapport_maquette.pdf via un mini-serveur local.
L’usage principal est le bouton « Télécharger » sur la page Rapports (route Flask).

  python scripts/export_maquette_pdf.py
  python scripts/export_maquette_pdf.py --periode all --dept Cardiologie
"""

from __future__ import annotations

import argparse
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "static" / "exports"
OUT_PDF = OUT_DIR / "rapport_maquette.pdf"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _make_url(port: int, ns: argparse.Namespace) -> str:
    q: dict[str, str] = {}
    if ns.periode:
        q["periode"] = ns.periode
    if ns.dept:
        q["dept"] = ns.dept
    if ns.sexe:
        q["sexe"] = ns.sexe
    if ns.maladie:
        q["maladie"] = ns.maladie
    if ns.traitement:
        q["traitement"] = ns.traitement
    base = f"http://127.0.0.1:{port}/rapport/maquette"
    if q:
        return base + "?" + urlencode(q)
    return base


def export_pdf(ns: argparse.Namespace | None = None) -> Path:
    if ns is None:
        ns = argparse.Namespace(periode="", dept="", sexe="", maladie="", traitement="")

    from werkzeug.serving import make_server

    from app import app
    from reporting.maquette_pdf import write_maquette_pdf_to_path

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    port = _free_port()
    url = _make_url(port, ns)

    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.4)

    try:
        write_maquette_pdf_to_path(url, OUT_PDF)
    finally:
        try:
            server.shutdown()
        except Exception:
            pass

    print(f"Écrit : {OUT_PDF}")
    return OUT_PDF


def main() -> None:
    ap = argparse.ArgumentParser(description="PDF rapport maquette A4 (CLI)")
    ap.add_argument("--periode", default="", help="Filtre : 30, 90, 365 ou all")
    ap.add_argument("--dept", default="", help="Département (un seul)")
    ap.add_argument("--sexe", default="")
    ap.add_argument("--maladie", default="")
    ap.add_argument("--traitement", default="")
    args = ap.parse_args()
    export_pdf(args)


if __name__ == "__main__":
    main()
