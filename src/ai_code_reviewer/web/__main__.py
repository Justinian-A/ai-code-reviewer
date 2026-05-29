"""Entry point for running the web server with `python -m ai_code_reviewer.web`."""

import threading
import webbrowser

import uvicorn


def open_browser():
    """Open browser after server starts."""
    webbrowser.open("http://localhost:8080")


if __name__ == "__main__":
    # Open browser after 1.5 second delay
    threading.Timer(1.5, open_browser).start()

    uvicorn.run(
        "ai_code_reviewer.web.app:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )
