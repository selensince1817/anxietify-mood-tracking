"""Spotify data fetching + mood analysis pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from cydets.algorithm import detect_cycles
from spotipy.exceptions import SpotifyException

logger = logging.getLogger(__name__)

TRACK_KEYS_TO_DROP = {
    "album",
    "available_markets",
    "disc_number",
    "external_ids",
    "external_urls",
    "preview_url",
    "type",
    "href",
    "track_number",
    "uri",
    "analysis_url",
}
AUDIO_FEATURE_KEYS_TO_DROP = {"id", "uri", "duration_ms", "type", "track_href"}


@dataclass
class MoodProfile:
    """Container for the aggregated Spotify mood information."""

    periods: Dict[str, Any]
    labels: List[str]
    values: List[float]
    rolling_window: int


def build_mood_profile(spotify_client, rolling_window: int = 60) -> MoodProfile:
    """Fetch and process a user's saved tracks into mood insights."""

    library_df = _fetch_library_dataframe(spotify_client)
    total_rows = library_df.shape[0]
    logger.info("Fetched %s saved tracks", total_rows)

    if total_rows < 150:
        raise ValueError("Too few saved tracks to analyze")

    window = 100 if total_rows > 1000 else max(rolling_window, 60)
    prepared_df = _prepare_dataframe(library_df)

    time_series = _rolling_valence_series(prepared_df, window)
    ma_series = _moving_average_series(prepared_df, time_series)

    cycles = detect_cycles(time_series, drop_zero_docs=True)
    processed_cycles = _process_cycles(cycles, duration_lowprecut=5, duration_lowcut=20, n_std=40)
    processed_cycles = processed_cycles.sort_values("doc", ascending=False)[:10]

    periods_df = _build_periods_dataframe(processed_cycles, prepared_df)

    return MoodProfile(
        periods=json.loads(periods_df.to_json()),
        labels=ma_series.index.tolist(),
        values=ma_series.values.tolist(),
        rolling_window=window,
    )


def _fetch_library_dataframe(spotify_client, batch_size: int = 50) -> pd.DataFrame:
    """Retrieve the entire saved tracks library together with audio features."""

    frames: List[pd.DataFrame] = []
    offset = 0
    total_tracks = None

    while True:
        batch_df, total_tracks = _fetch_saved_tracks(
            spotify_client, limit=batch_size, offset=offset
        )
        if batch_df.empty:
            break

        features_df = _fetch_audio_features(spotify_client, batch_df["id"].tolist())
        combined = pd.concat([features_df.reset_index(drop=True), batch_df.reset_index(drop=True)], axis=1)
        frames.append(combined)

        offset += batch_size
        if total_tracks is not None and offset >= total_tracks:
            break

        if batch_df.shape[0] < batch_size:
            break

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def _fetch_saved_tracks(spotify_client, limit: int = 50, offset: int = 0) -> Tuple[pd.DataFrame, int]:
    result = spotify_client.current_user_saved_tracks(limit=limit, offset=offset)
    playlist_size = result.get("total", 0)

    simplified_tracks: List[Dict[str, Any]] = []
    for item in result.get("items", []):
        track = dict(item.get("track", {}))
        artists = [artist.get("name") for artist in track.get("artists", []) if artist.get("name")]
        trimmed_track = {key: value for key, value in track.items() if key not in TRACK_KEYS_TO_DROP}
        trimmed_track["artists"] = ", ".join(artists)
        trimmed_track["added_at"] = item.get("added_at")
        simplified_tracks.append(trimmed_track)

    if not simplified_tracks:
        return pd.DataFrame(), playlist_size

    dataframe = pd.DataFrame(simplified_tracks)
    return dataframe, playlist_size


def _fetch_audio_features(spotify_client, track_ids: Sequence[str]) -> pd.DataFrame:
    """Fetch audio features in small batches while preserving track order."""

    def flush(buffer: List[str], positions: List[int]) -> List[Tuple[int, Dict[str, Any]]]:
        if not buffer:
            return []
        try:
            response = spotify_client.audio_features(tracks=buffer)
        except SpotifyException:
            raise

        batch_records: List[Tuple[int, Dict[str, Any]]] = []
        for pos, feature in zip(positions, response):
            if feature is None:
                batch_records.append((pos, {}))
                continue
            filtered = {
                key: value
                for key, value in feature.items()
                if key not in AUDIO_FEATURE_KEYS_TO_DROP
            }
            batch_records.append((pos, filtered))
        return batch_records

    ordered_features: Dict[int, Dict[str, Any]] = {}
    buffer_ids: List[str] = []
    buffer_positions: List[int] = []
    batch_size = 20

    for idx, track_id in enumerate(track_ids):
        if not track_id or not isinstance(track_id, str):
            ordered_features[idx] = {}
            continue
        buffer_ids.append(track_id)
        buffer_positions.append(idx)

        if len(buffer_ids) >= batch_size:
            for pos, record in flush(buffer_ids, buffer_positions):
                ordered_features[pos] = record
            buffer_ids.clear()
            buffer_positions.clear()

    for pos, record in flush(buffer_ids, buffer_positions):
        ordered_features[pos] = record

    rows = [ordered_features.get(idx, {}) for idx in range(len(track_ids))]
    return pd.DataFrame(rows)


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy().reset_index(drop=True)
    working["playlist_place"] = np.flip(np.arange(0, len(working)))
    working.drop(["is_local", "uri"], axis=1, inplace=True, errors="ignore")

    if "explicit" in working.columns:
        working["explicit"] = working["explicit"].replace({True: 1, False: 0}).astype(int)

    if "popularity" in working.columns:
        working["popularity"] = working["popularity"] / 100

    working.sort_values("playlist_place", ascending=True, inplace=True)
    working.reset_index(drop=True, inplace=True)
    return working


def _rolling_valence_series(df: pd.DataFrame, rolling_window: int) -> pd.Series:
    valence_series = pd.Series(data=np.array(df["valence"]), name="valence", index=df["playlist_place"])
    valence_series = valence_series.sort_index()
    return valence_series.rolling(window=rolling_window).mean()


def _moving_average_series(df: pd.DataFrame, time_series: pd.Series) -> pd.Series:
    dates_df = pd.DataFrame({"added_at": df["added_at"].values})
    ma_df = pd.concat([dates_df, pd.DataFrame({"valence": time_series})], axis=1, join="outer")
    ma_df.set_index("added_at", inplace=True)
    ma_df["valence"] = ma_df["valence"].values[::-1]
    ma_series = ma_df["valence"].dropna()
    ma_series.index = ma_series.index.map(_format_date)
    return ma_series


def _process_cycles(
    cycles: pd.DataFrame,
    *,
    duration_lowprecut: int,
    duration_lowcut: int,
    n_std: int,
    duration_upcut: int = 10000,
) -> pd.DataFrame:
    filtered = cycles.loc[cycles["duration"] > duration_lowprecut]
    mean = np.mean(filtered["duration"], axis=0)
    sd = np.std(filtered["duration"], axis=0)

    mask = (filtered["duration"] < mean + (n_std * sd)) & (filtered["duration"] > mean - (n_std * sd))
    cycles_outliered = filtered.loc[mask]
    cycl = cycles_outliered.loc[cycles_outliered["duration"] > duration_lowcut]
    cycl = cycl.loc[cycl["duration"] < duration_upcut]
    return cycl


def _build_periods_dataframe(cycles: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "start_date",
        "end_date",
        "min_date",
        "duration_days",
        "duration_entries",
        "cycle_depth",
        "song_start_name",
        "song_end_name",
        "song_min_name",
        "song_start_uri",
        "song_min_uri",
        "song_end_uri",
        "song_start_index",
        "song_end_index",
    ]

    periods = pd.DataFrame(columns=columns)

    for idx, row in cycles.iterrows():
        song_start = df.iloc[int(row["t_start"])]
        song_end = df.iloc[int(row["t_end"])]
        song_min = df.iloc[int(row["t_minimum"])]

        start_date = _parse_iso(song_start["added_at"])
        end_date = _parse_iso(song_end["added_at"])
        min_date = _parse_iso(song_min["added_at"])

        delta_days = (end_date - start_date).days
        delta_entries = abs(int(song_end["playlist_place"]) - int(song_start["playlist_place"]))

        periods.loc[len(periods)] = [
            _format_pretty_date(start_date),
            _format_pretty_date(end_date),
            _format_pretty_date(min_date),
            delta_days,
            delta_entries,
            row["doc"],
            f"{song_start['name']} - {song_start['artists']}",
            f"{song_end['name']} - {song_end['artists']}",
            f"{song_min['name']} - {song_min['artists']}",
            song_start["id"],
            song_min["id"],
            song_end["id"],
            int(song_start["playlist_place"]),
            int(song_end["playlist_place"]),
        ]

    return periods


def _parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _format_pretty_date(value: datetime) -> str:
    return f"{value.day} of {value.strftime('%B')}, {value.year}"


def _format_date(value: str) -> str:
    return _format_pretty_date(_parse_iso(value))
