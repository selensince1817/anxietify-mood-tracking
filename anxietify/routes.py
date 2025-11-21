"""HTTP routes for the Anxietify web experience."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Tuple

from flask import Blueprint, current_app, redirect, render_template, request, session
from spotipy import Spotify, SpotifyException
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from anxietify.services import build_mood_profile

web_bp = Blueprint("web", __name__)


def _ensure_user_uuid() -> str:
    """Guarantee that the visiting user has a UUID stored in the session."""
    user_uuid = session.get("uuid")
    if user_uuid:
        return user_uuid
    user_uuid = str(uuid.uuid4())
    session["uuid"] = user_uuid
    return user_uuid


def _cache_handler() -> CacheFileHandler:
    """Return a cache handler pointing at the user's Spotify cache file."""
    cache_dir = Path(current_app.config["SPOTIFY_CACHE_DIR"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / _ensure_user_uuid()
    current_app.logger.debug("Using Spotify cache file at %s", cache_path)
    return CacheFileHandler(cache_path=str(cache_path))


def _auth_manager(
    scope: str | None = None,
) -> Tuple[SpotifyOAuth, CacheFileHandler]:
    """Build an auth manager plus cache handler pair."""
    cache_handler = _cache_handler()
    auth_manager = SpotifyOAuth(
        scope=scope or current_app.config["SPOTIFY_SCOPE"],
        cache_handler=cache_handler,
        show_dialog=True,
    )
    return auth_manager, cache_handler


def _spotify_client(auth_manager: SpotifyOAuth) -> Spotify:
    """Return an authenticated Spotify API client."""
    return Spotify(auth_manager=auth_manager)


@web_bp.route("/")
def index():
    """Landing page / Spotify auth handshake."""
    auth_manager, cache_handler = _auth_manager()

    if request.args.get("code"):
        auth_manager.get_access_token(request.args.get("code"))
        return redirect("/")

    cached_token = cache_handler.get_cached_token()
    current_app.logger.debug("Index view token present: %s", bool(cached_token))
    if not auth_manager.validate_token(cached_token):
        auth_url = auth_manager.get_authorize_url()
        return render_template(
            "index.html",
            authorization_url=auth_url,
            logged_in=False,
        )

    return render_template(
        "index.html",
        authorization_url="/",
        logged_in=True,
    )


@web_bp.route("/fetch")
def fetch():
    """Kick off data ingestion + analysis."""
    auth_manager, cache_handler = _auth_manager()

    token_info = cache_handler.get_cached_token()
    current_app.logger.debug("Fetch view token present: %s", bool(token_info))
    if not auth_manager.validate_token(token_info):
        return redirect("/")

    spotify_client = _spotify_client(auth_manager)

    try:
        user_profile = spotify_client.me()
        current_app.logger.info("Start fetch for %s", user_profile.get("display_name"))
    except SpotifyException:
        current_app.logger.warning("Spotify profile unavailable for current session")
        return render_template("beta.html")

    try:
        mood_profile = build_mood_profile(spotify_client)
    except ValueError as exc:
        current_app.logger.warning("Insufficient data for analysis: %s", exc)
        return render_template("beta.html")
    except SpotifyException as exc:
        current_app.logger.exception("Spotify API error during fetch: %s", exc)
        error_message = (
            "Spotify denied one of the API calls (status {}). "
            "If this account should have access, double-check it is added as a tester in the Spotify dashboard."
        ).format(getattr(exc, "http_status", "unknown"))
        return render_template(
            "error.html",
            title="Spotify access issue",
            message=error_message,
        ), 502
    except Exception as exc:  # noqa: BLE001 - keep broad for now, log for debugging
        current_app.logger.exception("Data fetch failed: %s", exc)
        return render_template(
            "error.html",
            title="Unexpected error",
            message="Something went wrong while building your mood profile. Please try again.",
        ), 500

    session["periods_json"] = mood_profile.periods
    session["labels"] = mood_profile.labels
    session["values"] = mood_profile.values
    session["rolling_window"] = mood_profile.rolling_window

    current_app.logger.info("Successful fetch for %s", user_profile.get("display_name"))
    return redirect("/display_general")


@web_bp.route("/display_general")
def display_general():
    """Render the overall valence chart."""
    auth_manager, cache_handler = _auth_manager()
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect("/")

    labels = session.get("labels")
    values = session.get("values")
    rolling_window = session.get("rolling_window", 0)

    if not (labels and values):
        return redirect("/fetch")

    return render_template(
        "display_chart.html",
        labels=labels[rolling_window:],
        values=values[rolling_window:],
    )


@web_bp.route("/display_periods")
def display_periods():
    """Render detected mood cycles."""
    auth_manager, cache_handler = _auth_manager()
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect("/")

    periods_json = session.get("periods_json")
    labels = session.get("labels")
    values = session.get("values")

    if not (periods_json and labels and values):
        return redirect("/fetch")

    start_indices = [idx - 3 for idx in periods_json["song_start_index"].values()]
    end_indices = [idx + 3 for idx in periods_json["song_end_index"].values()]

    values_windows = []
    labels_windows = []
    for start, end in zip(start_indices, end_indices):
        values_windows.append(values[start:end])
        labels_windows.append(labels[start:end])

    period_cards = []
    period_order = sorted(periods_json["start_date"].keys(), key=int)
    for idx, key in enumerate(period_order):
        period_cards.append(
            {
                "number": idx + 1,
                "start_date": periods_json["start_date"][key],
                "end_date": periods_json["end_date"][key],
                "min_date": periods_json["min_date"][key],
                "song_start_uri": periods_json["song_start_uri"][key],
                "song_end_uri": periods_json["song_end_uri"][key],
                "song_min_uri": periods_json["song_min_uri"][key],
                "labels": labels_windows[idx],
                "values": values_windows[idx],
                "canvas_id": f"lineChart-{idx + 1}",
            }
        )

    return render_template(
        "display_periods.html",
        periods=period_cards,
    )


@web_bp.route("/sign_out")
def sign_out():
    """Flush Spotify + Flask session state."""
    session.clear()
    return redirect("/")
