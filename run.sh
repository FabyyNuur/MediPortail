#!/bin/bash
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
export FLASK_DEBUG="${FLASK_DEBUG:-1}"
echo "Démarrage MediPortail (Flask) sur http://127.0.0.1:${PORT:-5050}"
exec python app.py
