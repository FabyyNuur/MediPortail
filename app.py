"""
MediPortail — application Flask (remplace l’ancienne app Dash).
"""

import os

from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-medportail-change-in-prod")

    @app.context_processor
    def _ctx_year():
        from datetime import datetime

        return {"moment_year": datetime.now().year}

    from routes.api import bp as api_bp
    from routes.main import bp as main_bp
    from routes.patients import bp as patients_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(api_bp)
    return app


app = create_app()


if __name__ == "__main__":
    # 5050 par défaut : sur macOS le port 5000 est souvent pris par AirPlay Receiver.
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
