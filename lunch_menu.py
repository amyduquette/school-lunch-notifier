"""Retrieve and print Central Elementary's lunch menu for a chosen date."""

import argparse
from datetime import date
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


API_BASE = (
    "https://msad35.api.nutrislice.com/menu/api/digest/"
    "school/central-elementary/menu-type/lunch/date"
)


def fetch_menu(target_date: date) -> dict:
    """Fetch the menu, rejecting unexpected data instead of showing wrong choices."""
    url = f"{API_BASE}/{target_date.year}/{target_date.month}/{target_date.day}/"
    with urlopen(url, timeout=20) as response:
        menu = json.load(response)

    if not isinstance(menu, dict) or menu.get("date") != target_date.isoformat():
        raise ValueError("Nutrislice returned an unexpected menu date or format.")

    items = menu.get("menu_items")
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise ValueError("Nutrislice returned an unexpected menu_items format.")

    notice = menu.get("holiday_text")
    if notice is not None and not isinstance(notice, str):
        raise ValueError("Nutrislice returned an unexpected holiday_text format.")

    return menu


def format_menu(target_date: date, menu: dict) -> str:
    """Format choices, or explain why there is no menu to display."""
    heading = f"Central Elementary lunch\n{target_date:%A, %B %d, %Y}"
    notice = (menu.get("holiday_text") or "").strip()
    if notice:
        return f"{heading}\n\nSchool notice: {notice}\nNo lunch menu to display."

    items = [item.strip() for item in menu["menu_items"] if item.strip()]
    if not items:
        return (
            f"{heading}\n\nNo lunch menu is available. "
            "This may be a day without lunch or a menu that has not been published."
        )

    choices = "\n".join(f"- {item}" for item in items)
    return f"{heading}\n\n{choices}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        required=True,
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Date of the lunch menu to retrieve.",
    )
    args = parser.parse_args()

    try:
        menu = fetch_menu(args.date)
    except (URLError, OSError, ValueError) as exc:
        print(f"Could not retrieve a valid lunch menu for {args.date}: {exc}", file=sys.stderr)
        return 1

    print(format_menu(args.date, menu))
    return 0


if __name__ == "__main__":
    sys.exit(main())
