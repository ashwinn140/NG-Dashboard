"""Offline mail transport and authentication integration regression tests."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import mailer


class MailerTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        mailer.OUTBOX.clear()

    def configure(self):
        os.environ.update(MAIL_PROVIDER="resend", RESEND_API_KEY="test-only-key", RESEND_FROM_EMAIL="Dashboard <onboarding@resend.dev>")

    def test_configuration_requires_key_and_sender(self):
        os.environ["MAIL_PROVIDER"] = "resend"
        self.assertFalse(mailer.configured())
        os.environ["RESEND_API_KEY"] = "test-only-key"
        self.assertFalse(mailer.configured())
        os.environ["RESEND_FROM_EMAIL"] = "onboarding@resend.dev"
        self.assertTrue(mailer.configured())

    def test_unknown_provider_fails_closed(self):
        self.configure()
        os.environ["MAIL_PROVIDER"] = "unknown"
        self.assertFalse(mailer.configured())

    @patch("app.mailer.http.client.HTTPSConnection")
    def test_https_payload_and_success(self, transport):
        self.configure()
        transport.return_value.getresponse.return_value.status = 200
        self.assertTrue(mailer.send("owner@example.com", "Sign in", "Private link", "<p>Private link</p>"))
        transport.assert_called_once()
        self.assertEqual(transport.call_args.args[0], "api.resend.com")
        self.assertEqual(transport.call_args.kwargs["timeout"], 20)
        self.assertTrue(transport.call_args.kwargs["context"].check_hostname)
        args, kwargs = transport.return_value.request.call_args
        self.assertEqual(args, ("POST", "/emails"))
        self.assertEqual(json.loads(kwargs["body"]), {"from": "Dashboard <onboarding@resend.dev>", "to": ["owner@example.com"], "subject": "Sign in", "text": "Private link", "html": "<p>Private link</p>"})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-only-key")
        transport.return_value.close.assert_called_once()

    @patch("app.mailer.smtplib.SMTP")
    @patch("app.mailer.http.client.HTTPSConnection")
    def test_rejection_is_safe_and_does_not_fall_back(self, transport, smtp):
        self.configure()
        transport.return_value.getresponse.return_value.status = 403
        transport.return_value.getresponse.return_value.read.return_value = b'private response with test-only-key'
        with self.assertLogs("mailer", level="ERROR") as logs:
            self.assertFalse(mailer.send("owner@example.com", "Sign in", "Private link"))
        self.assertIn("403", " ".join(logs.output))
        self.assertNotIn("test-only-key", " ".join(logs.output))
        self.assertNotIn("Private link", " ".join(logs.output))
        smtp.assert_not_called()
        transport.return_value.close.assert_called_once()

    @patch("app.mailer.http.client.HTTPSConnection")
    def test_network_failure_does_not_leak_exception_details(self, transport):
        self.configure()
        transport.return_value.request.side_effect = TimeoutError("test-only-key Private link")
        with self.assertLogs("mailer", level="ERROR") as logs:
            self.assertFalse(mailer.send("owner@example.com", "Sign in", "Private link"))
        self.assertIn("TimeoutError", " ".join(logs.output))
        self.assertNotIn("test-only-key", " ".join(logs.output))
        transport.return_value.close.assert_called_once()

    @patch("app.mailer.smtplib.SMTP")
    def test_existing_smtp_installations_still_work(self, smtp):
        os.environ.update(SMTP_HOST="smtp.example.com", SMTP_USER="owner@example.com", SMTP_PASSWORD="test-only-password")
        self.assertTrue(mailer.configured())
        self.assertTrue(mailer.send("user@example.com", "Hello", "Body"))
        smtp.return_value.__enter__.return_value.starttls.assert_called_once()
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()

    @patch("app.mailer.http.client.HTTPSConnection")
    def test_unconfigured_does_not_call_network(self, transport):
        os.environ["MAIL_PROVIDER"] = "resend"
        self.assertFalse(mailer.send("owner@example.com", "Hello", "Body"))
        transport.assert_not_called()

    @patch("app.mailer.http.client.HTTPSConnection")
    def test_real_login_request_uses_https_and_keeps_password_login(self, transport):
        from fastapi.testclient import TestClient
        from app.db import get_engine
        from app.server import create_app
        self.configure()
        os.environ.update(ADMIN_EMAIL="owner@example.com", ADMIN_PASSWORD="Test-password123", SECRET_KEY="test-only-secret", INGEST_SECRET="test-only-ingest")
        transport.return_value.getresponse.return_value.status = 200
        with tempfile.TemporaryDirectory() as tmp:
            engine = get_engine("sqlite:///" + os.path.join(tmp, "test.db"))
            app = create_app(engine, os.path.join(tmp, "uploads"))
            with TestClient(app) as client:
                self.assertTrue(client.get("/auth/options").json()["email"])
                self.assertEqual(client.post("/auth/request", json={"email": "owner@example.com"}).status_code, 200)
                payload = json.loads(transport.return_value.request.call_args.kwargs["body"])
                self.assertIn("/auth/verify?t=", payload["text"])
                calls = transport.call_count
                self.assertEqual(client.post("/auth/request", json={"email": "unknown@example.com"}).status_code, 200)
                self.assertEqual(transport.call_count, calls)
                self.assertEqual(client.post("/auth/login", json={"login": "owner@example.com", "password": "Test-password123"}).status_code, 200)
            engine.dispose()


    @patch("app.mailer.http.client.HTTPSConnection")
    def test_resend_attachment_is_base64_encoded(self, transport):
        self.configure()
        transport.return_value.getresponse.return_value.status = 200
        self.assertTrue(mailer.send("owner@example.com", "Report", "Attached",
            attachments=[{"filename": "daily.xlsx", "content": b"workbook", "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]))
        payload = json.loads(transport.return_value.request.call_args.kwargs["body"])
        self.assertEqual(payload["attachments"], [{"filename": "daily.xlsx", "content": "d29ya2Jvb2s="}])
        self.assertEqual(mailer.OUTBOX[-1]["attachments"], [{"filename": "daily.xlsx", "size": 8}])

    def test_attachment_size_and_filename_limits_fail_closed(self):
        self.assertFalse(mailer.send("owner@example.com", "Report", "Body",
            attachments=[{"filename": "../secrets.xlsx", "content": b"x"}]))
        self.assertFalse(mailer.send("owner@example.com", "Report", "Body",
            attachments=[{"filename": "huge.xlsx", "content": b"x" * (mailer.MAX_ATTACHMENT_BYTES + 1)}]))

    @patch("app.mailer.smtplib.SMTP")
    def test_smtp_attachment_is_attached_to_message(self, smtp):
        os.environ.update(SMTP_HOST="smtp.example.com", SMTP_USER="owner@example.com", SMTP_PASSWORD="test-only-password")
        self.assertTrue(mailer.send("user@example.com", "Report", "Body",
            attachments=[{"filename": "daily.csv", "content": b"a,b\n1,2", "content_type": "text/csv"}]))
        msg = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertTrue(any(part.get_filename() == "daily.csv" for part in msg.walk()))

if __name__ == "__main__":
    unittest.main()
