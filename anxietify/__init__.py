"""Application factory for the Anxietify Flask app."""

from __future__ import annotations

from pathlib import Path
from typing import Type

from dotenv import load_dotenv
from flask import Flask

from .config import Config
from .extensions import session_ext
from .routes import web_bp

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(config_class: Type[Config] = Config) -> Flask:
    """Create and configure the Flask application instance."""
    load_dotenv(BASE_DIR / ".env")
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_class)

    Path(app.config["SESSION_FILE_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["SPOTIFY_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)

    session_ext.init_app(app)
    app.register_blueprint(web_bp)

    return app

