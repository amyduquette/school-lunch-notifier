"""Preview a lunch email, or send it through Gmail with --send."""

import argparse
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate
import os
import re
import smtplib
import ssl
import sys
from zoneinfo import ZoneInfo

from lunch_menu import fetch_menu, format_menu


MENU_URL = "https://msad35.nutrislice.com/menu/central-elementary/lunch/"
EASTERN = ZoneInfo("America/New_York")


class DeliveryError(Exception):
    """A rejected email or a request whose delivery status needs checking."""


def skip_reason(target_date: date, menu: dict) -> str | None:
    """Return why this menu should not be emailed, if applicable."""
    if target_date.weekday() >= 5:
        return "the target date is a weekend"
    if (menu.get("holiday_text") or "").strip():
        return "the school published a notice instead of a lunch menu"
    if not any(item.strip() for item in menu["menu_items"]):
        return "no lunch choices have been published"
    return None


def compose_email(target_date: date, menu: dict, test: bool = False) -> tuple[str, str]:
    """Reuse the menu formatting for a clear subject and plain-text email."""
    prefix = "[TEST] " if test else ""
    subject = f"{prefix}Central Elementary lunch - {target_date:%A, %B %d, %Y}"
    body = f"{format_menu(target_date, menu)}\n\nSchool menu: {MENU_URL}\n"
    return subject, body


def email_settings() -> tuple[str, str, list[str]]:
    """Read credentials and addresses without exposing them in error messages."""
    names = ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_RECIPIENTS")
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name in names if not values[name]]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    # Google displays app passwords in groups separated by spaces.
    password = "".join(values["GMAIL_APP_PASSWORD"].split())
    if len(password) != 16:
        raise ValueError("GMAIL_APP_PASSWORD must contain 16 characters; spaces are ignored.")

    sender = values["GMAIL_ADDRESS"]
    recipients = list(
        dict.fromkeys(
            address.strip()
            for address in values["EMAIL_RECIPIENTS"].split(",")
            if address.strip()
        )
    )
    address_pattern = r"[^@\s<>,]+@[^@\s<>,]+\.[^@\s<>,]+"
    if not re.fullmatch(address_pattern, sender):
        raise ValueError("GMAIL_ADDRESS must be a single email address without a display name.")
    if not recipients or any(not re.fullmatch(address_pattern, address) for address in recipients):
        raise ValueError("EMAIL_RECIPIENTS must be a comma-separated list of email addresses.")
    return password, sender, recipients


def send_email(
    subject: str, body: str, password: str, sender: str, recipients: list[str]
) -> None:
    """Send over verified TLS; never retry an uncertain send automatically."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message["Date"] = formatdate()
    message.set_content(body)

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com", 465, timeout=20, context=ssl.create_default_context()
        ) as smtp:
            smtp.login(sender, password)
            refused = smtp.send_message(message, from_addr=sender, to_addrs=recipients)
    except smtplib.SMTPAuthenticationError:
        raise DeliveryError(
            "Gmail rejected sign-in. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
        ) from None
    except smtplib.SMTPRecipientsRefused:
        raise DeliveryError(
            "Gmail refused all recipient addresses. Check EMAIL_RECIPIENTS."
        ) from None
    except (smtplib.SMTPException, OSError):
        raise DeliveryError(
            "The Gmail connection or send failed. Delivery status may be unknown; "
            "check Gmail's Sent folder before retrying."
        ) from None

    if refused:
        raise DeliveryError(
            f"Gmail refused {len(refused)} recipient(s); other recipients may have been "
            "accepted. Check Gmail's Sent folder before retrying."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    date_selection = parser.add_mutually_exclusive_group()
    date_selection.add_argument(
        "--date", type=date.fromisoformat, metavar="YYYY-MM-DD",
        help="Menu date; defaults to tomorrow in Eastern Time.",
    )
    date_selection.add_argument(
        "--scheduled", action="store_true",
        help="Only run during the 6 PM Eastern hour, Sunday through Thursday.",
    )
    parser.add_argument(
        "--send", action="store_true",
        help="Send email; without this flag, only preview it.",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Prefix the subject with [TEST]. Does not bypass menu checks.",
    )
    args = parser.parse_args()
    now = datetime.now(EASTERN)
    if args.scheduled and (now.weekday() not in {0, 1, 2, 3, 6} or now.hour != 18):
        print("Skipped: scheduled emails only run from 6:00 to 6:59 PM Eastern, Sunday through Thursday.")
        return 0
    target_date = args.date or (now.date() + timedelta(days=1))

    if target_date.weekday() >= 5:
        print(f"Skipped {target_date}: the target date is a weekend.")
        return 0

    try:
        menu = fetch_menu(target_date)
    except (OSError, ValueError) as exc:
        print(f"Could not retrieve a valid lunch menu for {target_date}: {exc}", file=sys.stderr)
        return 1

    reason = skip_reason(target_date, menu)
    if reason:
        print(f"Skipped {target_date}: {reason}.")
        return 0

    subject, body = compose_email(target_date, menu, test=args.test)
    if not args.send:
        print(f"PREVIEW (no email sent)\nSubject: {subject}\n\n{body}")
        return 0

    try:
        password, sender, recipients = email_settings()
        send_email(subject, body, password, sender, recipients)
    except (ValueError, DeliveryError) as exc:
        print(f"Email not confirmed: {exc}", file=sys.stderr)
        return 1

    print(f"Gmail accepted the {target_date} menu for delivery to {len(recipients)} recipient(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
