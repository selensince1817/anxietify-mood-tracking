"""Configuration objects for the Anxietify application."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base configuration shared across environments."""

    SECRET_KEY = os.getenv("CLI_SECRET", "change-me")

    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = str(BASE_DIR / ".flask_session")
    SESSION_COOKIE_NAME = "anxietify-session"

    SPOTIFY_SCOPE = os.getenv("SPOTIFY_SCOPE", "user-library-read")
    SPOTIFY_CACHE_DIR = str(BASE_DIR / ".spotify_caches")

    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    """Configuration defaults for local development."""

    DEBUG = True


class ProductionConfig(Config):
    """Configuration defaults for production deployments."""

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = "https"

