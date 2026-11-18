"""Serve Central Elementary's lunch menu as a small Flask web app."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, Response, request

from lunch_menu import fetch_menu, format_menu


app = Flask(__name__)
EASTERN = ZoneInfo("America/New_York")


@app.get("/")
def index() -> Response:
    """Show tomorrow's menu, or a date supplied as ?date=YYYY-MM-DD."""
    date_text = request.args.get("date")
    if date_text is None:
        target_date = datetime.now(EASTERN).date() + timedelta(days=1)
    else:
        try:
            target_date = date.fromisoformat(date_text)
        except ValueError:
            return Response(
                "Invalid date. Use ?date=YYYY-MM-DD.\n",
                status=400,
                mimetype="text/plain",
            )

    try:
        menu = fetch_menu(target_date)
    except (OSError, ValueError) as exc:
        app.logger.warning("Could not retrieve lunch menu for %s: %s", target_date, exc)
        return Response(
            f"The lunch menu for {target_date} is temporarily unavailable. "
            "Please try again later.\n",
            status=502,
            mimetype="text/plain",
        )

    return Response(format_menu(target_date, menu) + "\n", mimetype="text/plain")


@app.get("/health")
def health() -> Response:
    """Let Render check that the app is running without calling Nutrislice."""
    return Response("ok\n", mimetype="text/plain")
