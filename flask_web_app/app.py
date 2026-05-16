"""Flask entry point.

Registers blueprints for vitals (`/api/vitals`), verdicts (`/api/verdict`),
and Kirby chat (`/api/chat/*`). Renders the dashboard at `/`.
"""

from flask import Flask, render_template

from config import Config
from routes.chat import bp as chat_bp
from routes.debug import bp as debug_bp
from routes.export import bp as export_bp
from routes.map_nav import bp as map_nav_bp
from routes.profile import bp as profile_bp
from routes.vitals import bp as vitals_bp
from routes.verdict import bp as verdict_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(vitals_bp)
    app.register_blueprint(verdict_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(map_nav_bp)

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            polling_interval_ms=app.config["POLLING_INTERVAL_MS"],
        )

    # Inbound Telegram polling. No-op when disabled or token missing.
    from telegram_bot import start_polling_thread
    start_polling_thread(app)

    return app


app = create_app()
