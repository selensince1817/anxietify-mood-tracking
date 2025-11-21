"""Compatibility layer for the legacy initial_fetch import path."""

from __future__ import annotations

from anxietify.services import MoodProfile, build_mood_profile


def get_json(spotify_object, rolling_window: int = 60):
    """Retain the historical interface expected by the templates/views."""

    profile: MoodProfile = build_mood_profile(spotify_object, rolling_window)
    return profile.periods, profile.labels, profile.values, profile.rolling_window
