"""App entrypoint for running the Anxietify Flask server."""

from __future__ import annotations

import os

from anxietify import create_app

app = create_app()


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            os.environ.get("SPOTIPY_REDIRECT_URI", "8080").split(":")[-1],
        )
    )
    app.run(debug=app.config.get("DEBUG", False), threaded=True, port=port)
