"""Point d’entrée sous-processus : évite un deadlock si le worker Flask est synchrone."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python -m reporting.maquette_pdf_worker <url_absolue_maquette> <sortie.pdf>", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    out = Path(sys.argv[2])
    from reporting.maquette_pdf import write_maquette_pdf_to_path

    write_maquette_pdf_to_path(url, out)


if __name__ == "__main__":
    main()
