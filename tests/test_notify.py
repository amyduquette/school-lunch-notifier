"""Check that email delivery is explicit and never uses a missing menu."""

import contextlib
from datetime import date, datetime, timezone
import io
import os
import smtplib
import ssl
import sys
import unittest
from unittest.mock import patch
from urllib.error import URLError

import notify


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.target = date(2026, 11, 19)
        self.menu = {
            "date": self.target.isoformat(),
            "menu_items": ["Scrambled Eggs", "PB&J"],
            "holiday_text": None,
        }
        self.settings = {
            "GMAIL_APP_PASSWORD": "abcdefghijklmnop",
            "GMAIL_ADDRESS": "sender@example.com",
            "EMAIL_RECIPIENTS": "parent1@example.com,parent2@example.com",
        }

    def run_command(self, *args, menu=None, error=None, settings=None, delivery_error=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, "argv", ["notify.py", *args]),
            patch.dict(os.environ, self.settings if settings is None else settings, clear=True),
            patch("notify.fetch_menu", return_value=menu or self.menu, side_effect=error) as fetch,
            patch("notify.send_email", side_effect=delivery_error) as send,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = notify.main()
        return result, stdout.getvalue(), stderr.getvalue(), fetch, send

    def test_preview_never_sends_and_contains_the_menu_date(self):
        result, output, error, _, send = self.run_command("--date", "2026-11-19", settings={})
        self.assertEqual(result, 0)
        self.assertIn("PREVIEW (no email sent)", output)
        self.assertIn("Thursday, November 19, 2026", output)
        self.assertIn("- Scrambled Eggs\n- PB&J", output)
        self.assertEqual(error, "")
        send.assert_not_called()

    def test_missing_configuration_prevents_a_send(self):
        result, output, error, _, send = self.run_command("--date", "2026-11-19", "--send", settings={})
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertIn("Missing environment variables", error)
        send.assert_not_called()

    def test_delivery_failure_is_a_nonzero_exit_without_an_acceptance_message(self):
        result, output, error, _, send = self.run_command(
            "--date", "2026-11-19", "--send", delivery_error=notify.DeliveryError("test failure")
        )
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertIn("Email not confirmed", error)
        send.assert_called_once()

    def test_send_is_explicit_and_reports_acceptance(self):
        result, output, _, _, send = self.run_command("--date", "2026-11-19", "--test", "--send")
        self.assertEqual(result, 0)
        send.assert_called_once()
        self.assertTrue(send.call_args.args[0].startswith("[TEST] "))
        self.assertEqual(send.call_args.args[4], ["parent1@example.com", "parent2@example.com"])
        self.assertIn("accepted", output)

    def test_weekend_does_not_even_fetch_a_menu(self):
        result, output, _, fetch, send = self.run_command("--date", "2026-11-21", "--send")
        self.assertEqual(result, 0)
        self.assertIn("weekend", output)
        fetch.assert_not_called()
        send.assert_not_called()

    def test_holidays_and_empty_menus_never_send_even_in_test_mode(self):
        for menu in [dict(self.menu, holiday_text="No school"), dict(self.menu, menu_items=[]), dict(self.menu, menu_items=[" "])]:
            with self.subTest(menu=menu):
                result, output, _, _, send = self.run_command("--date", "2026-11-19", "--test", "--send", menu=menu)
                self.assertEqual(result, 0)
                self.assertIn("Skipped", output)
                send.assert_not_called()

    def test_menu_failure_never_sends(self):
        for error in [URLError("offline"), TimeoutError("timed out"), ValueError("wrong date")]:
            with self.subTest(error=error):
                result, _, output, _, send = self.run_command("--date", "2026-11-19", "--send", error=error)
                self.assertEqual(result, 1)
                self.assertIn("Could not retrieve a valid lunch menu", output)
                send.assert_not_called()

    def test_tomorrow_uses_eastern_time_in_winter_and_summer(self):
        for instant, expected in [
            (datetime(2026, 11, 19, 1, tzinfo=timezone.utc), date(2026, 11, 19)),
            (datetime(2026, 7, 2, 1, tzinfo=timezone.utc), date(2026, 7, 2)),
        ]:
            with self.subTest(instant=instant), patch("notify.datetime") as clock:
                clock.now.side_effect = lambda tz: instant.astimezone(tz)
                result, _, _, fetch, send = self.run_command()
                self.assertEqual(result, 0)
                fetch.assert_called_once_with(expected)
                send.assert_not_called()

    def test_scheduled_send_uses_six_pm_eastern_across_dst_changes(self):
        for instant, expected in [
            (datetime(2026, 11, 18, 23, tzinfo=timezone.utc), date(2026, 11, 19)),
            (datetime(2026, 7, 1, 22, tzinfo=timezone.utc), date(2026, 7, 2)),
            (datetime(2026, 3, 8, 22, tzinfo=timezone.utc), date(2026, 3, 9)),
            (datetime(2026, 11, 1, 23, tzinfo=timezone.utc), date(2026, 11, 2)),
        ]:
            with self.subTest(instant=instant), patch("notify.datetime") as clock:
                clock.now.side_effect = lambda tz: instant.astimezone(tz)
                result, _, _, fetch, send = self.run_command("--scheduled", "--send")
                self.assertEqual(result, 0)
                fetch.assert_called_once_with(expected)
                send.assert_called_once()
                self.assertFalse(send.call_args.args[0].startswith("[TEST]"))

    def test_scheduled_send_allows_a_delay_within_the_six_pm_hour(self):
        instant = datetime(2026, 11, 18, 23, 59, tzinfo=timezone.utc)
        with patch("notify.datetime") as clock:
            clock.now.side_effect = lambda tz: instant.astimezone(tz)
            result, _, _, _, send = self.run_command("--scheduled", "--send")
        self.assertEqual(result, 0)
        send.assert_called_once()

    def test_scheduled_send_skips_wrong_hours_and_days_without_fetching(self):
        for instant in [
            datetime(2026, 11, 18, 22, tzinfo=timezone.utc),  # 5 PM, winter
            datetime(2026, 7, 1, 23, tzinfo=timezone.utc),  # 7 PM, summer
            datetime(2026, 11, 19, 5, tzinfo=timezone.utc),  # midnight, too late
            datetime(2026, 11, 20, 23, tzinfo=timezone.utc),  # Friday, 6 PM
            datetime(2026, 11, 21, 23, tzinfo=timezone.utc),  # Saturday, 6 PM
        ]:
            with self.subTest(instant=instant), patch("notify.datetime") as clock:
                clock.now.side_effect = lambda tz: instant.astimezone(tz)
                result, output, _, fetch, send = self.run_command("--scheduled", "--send")
                self.assertEqual(result, 0)
                self.assertIn("Skipped", output)
                fetch.assert_not_called()
                send.assert_not_called()

    def test_scheduled_send_rejects_a_date_override(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                self.run_command("--scheduled", "--date", "2026-11-19", "--send")
        self.assertEqual(caught.exception.code, 2)

    def test_settings_allow_one_test_recipient_and_deduplicate_addresses(self):
        with patch.dict(os.environ, dict(self.settings, EMAIL_RECIPIENTS="parent@example.com, parent@example.com"), clear=True):
            _, _, recipients = notify.email_settings()
        self.assertEqual(recipients, ["parent@example.com"])

    def test_settings_accept_spaces_in_google_app_password(self):
        with patch.dict(
            os.environ, dict(self.settings, GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"), clear=True
        ):
            password, _, _ = notify.email_settings()
        self.assertEqual(password, "abcdefghijklmnop")

    def test_settings_reject_missing_values_and_invalid_addresses(self):
        for settings in [
            {},
            dict(self.settings, GMAIL_ADDRESS="invalid"),
            dict(self.settings, EMAIL_RECIPIENTS="invalid"),
            dict(self.settings, GMAIL_APP_PASSWORD="too-short"),
        ]:
            with self.subTest(names=list(settings)), patch.dict(os.environ, settings, clear=True):
                with self.assertRaises(ValueError):
                    notify.email_settings()

    def test_gmail_uses_verified_tls_and_sends_both_recipients(self):
        subject, body = notify.compose_email(self.target, self.menu)
        recipients = ["one@example.com", "two@example.com"]
        with patch("notify.smtplib.SMTP_SSL") as connect:
            smtp = connect.return_value.__enter__.return_value
            smtp.send_message.return_value = {}
            notify.send_email(subject, body, "abcdefghijklmnop", "sender@example.com", recipients)
        connect.assert_called_once()
        self.assertEqual(connect.call_args.args, ("smtp.gmail.com", 465))
        tls = connect.call_args.kwargs["context"]
        self.assertTrue(tls.check_hostname)
        self.assertEqual(tls.verify_mode, ssl.CERT_REQUIRED)
        smtp.login.assert_called_once_with("sender@example.com", "abcdefghijklmnop")
        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(str(message["Subject"]), subject)
        self.assertEqual(message.get_content(), body)
        self.assertEqual(message["To"], "one@example.com, two@example.com")
        self.assertEqual(smtp.send_message.call_args.kwargs["to_addrs"], recipients)

    def test_authentication_rejection_does_not_expose_server_details(self):
        with patch("notify.smtplib.SMTP_SSL") as connect:
            smtp = connect.return_value.__enter__.return_value
            smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"sensitive-server-detail")
            with self.assertRaises(notify.DeliveryError) as caught:
                notify.send_email("subject", "body", "abcdefghijklmnop", "sender@example.com", ["one@example.com"])
        self.assertIn("Gmail rejected sign-in", str(caught.exception))
        self.assertNotIn("sensitive-server-detail", str(caught.exception))
        smtp.send_message.assert_not_called()

    def test_refused_recipients_are_reported_without_exposing_addresses(self):
        refused = {"two@example.com": (550, b"rejected")}
        for result in [refused, smtplib.SMTPRecipientsRefused(refused)]:
            with self.subTest(result=type(result).__name__), patch("notify.smtplib.SMTP_SSL") as connect:
                smtp = connect.return_value.__enter__.return_value
                if isinstance(result, Exception):
                    smtp.send_message.side_effect = result
                else:
                    smtp.send_message.return_value = result
                with self.assertRaises(notify.DeliveryError) as caught:
                    notify.send_email(
                        "subject", "body", "abcdefghijklmnop", "sender@example.com",
                        ["one@example.com", "two@example.com"],
                    )
                self.assertIn("refused", str(caught.exception))
                self.assertNotIn("two@example.com", str(caught.exception))
                smtp.send_message.assert_called_once()

    def test_uncertain_send_is_not_retried(self):
        for result in [
            smtplib.SMTPServerDisconnected("disconnected"),
            TimeoutError("timed out"),
        ]:
            with self.subTest(result=type(result).__name__):
                with patch("notify.smtplib.SMTP_SSL") as connect:
                    smtp = connect.return_value.__enter__.return_value
                    smtp.send_message.side_effect = result
                    with self.assertRaises(notify.DeliveryError) as caught:
                        notify.send_email("subject", "body", "abcdefghijklmnop", "sender@example.com", ["one@example.com"])
                self.assertIn("Sent folder before retrying", str(caught.exception))
                smtp.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
