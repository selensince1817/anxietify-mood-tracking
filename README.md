# Anxietify

Anxietify visualises the emotional arc of your Spotify saved tracks. After authenticating with Spotify, the app fetches your library, derives rolling valence scores, detects mood “cycles”, and renders them via a Flask + Bulma front‑end.

## Features

- **Spotify OAuth flow** backed by server-side sessions and cache files per visitor.
- **Data pipeline** that fetches saved tracks, merges audio features, smooths valence via rolling means, and surfaces the most prominent cycles using `cydets`.
- **Responsive UI** with Bulma/Flickity + Chart.js, sharing a single base layout and JS renderer.
- **Deployment ready** thanks to `Procfile`, Gunicorn entrypoint, and a clean `.gitignore`.

## Project structure

```
.
├── anxietify/
│   ├── __init__.py          # Application factory & blueprint registration
│   ├── config.py            # Environment-specific configuration
│   ├── extensions.py        # Flask extensions (Session)
│   ├── routes.py            # HTTP endpoints + Spotify OAuth flow
│   └── services/
│       ├── __init__.py
│       └── mood_pipeline.py # Spotify fetch + analysis logic
├── templates/               # Jinja templates (extend base.html)
├── static/
│   ├── styles.css
│   └── js/mood-charts.js
├── app.py                   # Entry point (loads create_app)
├── initial_fetch.py         # Compatibility shim (legacy import path)
├── requirements.txt
└── Procfile
```

## Getting started

1. **Create a Spotify application**
   - Add redirect URIs for both local and prod environments, e.g. `http://127.0.0.1:5000` for local dev and `https://spotipy-moodify.herokuapp.com` for production.
   - Grab the `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, and `SPOTIPY_REDIRECT_URI`.

2. **Install dependencies**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure environment variables via `.env`**

   ```bash
   cp .env.example .env
   # then edit .env with your real Spotify credentials + secret key
   ```

   The app automatically loads `.env` (thanks to `python-dotenv`), so `flask run` works without manually exporting variables.

4. **Run locally**

   ```bash
   flask --app app run --debug
   # or
   python app.py
   ```

   The UI lives at `http://127.0.0.1:5000` by default (match this in your Spotify redirect settings).

## Deployment notes

- Gunicorn is configured in `Procfile`: `web: gunicorn app:app`.
- Session data and Spotify cache files are stored inside `.flask_session/` and `.spotify_caches/` (ignored in git). Ensure the filesystem is writable (e.g., use ephemeral disk on Heroku or mount persistent storage).
- The new service layer is pure Python/pandas, so it can be unit tested offline using stored Spotify responses.

## Important: Spotify API Restrictions (November 2024)

**Effective November 27, 2024, Spotify has restricted access to the `audio-features` endpoint for new applications and those in development mode.**

This application relies on `audio_features` (specifically `valence`) to calculate mood. If you are running this with a new Client ID or an app in "Development Mode," Spotify will return **403 Forbidden** errors during the fetch step.

**Workarounds:**
1. **Existing Extension:** If you have an older Client ID with extended access approval, use that credential.
2. **Request Extension:** Check your Spotify Developer Dashboard to see if you are eligible to request an extension for deprecated endpoints.
3. **Pivot:** Without `audio-features`, the mood analysis pipeline cannot function as originally designed.

## Troubleshooting

- **Missing cycles**: We require at least 150 saved tracks to produce meaningful rolling stats. The UI will show the beta page if the threshold isn’t met.
- **Expired sessions**: Use `/sign_out` to clear cached tokens if you ever get redirected back to the home screen unexpectedly.
- **Spotify rate limits**: The fetch step paginates in batches of 50 tracks. If you have thousands of saved tracks, expect a short loading pause while the analysis runs.

Questions or feature ideas? Open an issue or drop me a note at `selen.since.1817@gmail.com`. Happy mood tracking!
