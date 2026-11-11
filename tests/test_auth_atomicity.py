import os
import tempfile
import unittest
from datetime import datetime

from sqlalchemy import create_engine

from app import auth
from app.db import metadata


class TestAuthenticationAtomicity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.engine = create_engine("sqlite:///" + self.tmp.name, future=True)
        metadata.create_all(self.engine)
        self.now = datetime(2026, 11, 11, 12, 0, 0)
        self.user = auth.create_user(
            self.engine,
            "atomicity@example.test",
            role="operations",
            user_id="atomicity",
            password="SecurePass123",
        )

    def tearDown(self):
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def test_email_link_is_consumed_once(self):
        issued = auth.request_link(self.engine, self.user["email"], now=self.now)
        self.assertIsNotNone(issued)
        token, _code, _user = issued

        first = auth.use_token(self.engine, token, now=self.now)
        second = auth.use_token(self.engine, token, now=self.now)

        self.assertEqual(first["id"], self.user["id"])
        self.assertIsNone(second)

    def test_code_attempt_limit_is_enforced(self):
        issued = auth.request_link(self.engine, self.user["email"], now=self.now)
        self.assertIsNotNone(issued)
        _token, code, _user = issued
        wrong_code = f"{(int(code) + 1) % 1000000:06d}"

        for _ in range(auth.CODE_ATTEMPTS):
            self.assertIsNone(auth.use_code(
                self.engine, self.user["email"], wrong_code, now=self.now
            ))

        self.assertIsNone(auth.use_code(
            self.engine, self.user["email"], code, now=self.now
        ))

    def test_password_lockout_survives_subsequent_attempts(self):
        for _ in range(auth.PW_FAILS):
            user, _message = auth.password_login(
                self.engine, self.user["email"], "WrongPass123", now=self.now
            )
            self.assertIsNone(user)

        user, message = auth.password_login(
            self.engine, self.user["email"], "SecurePass123", now=self.now
        )
        self.assertIsNone(user)
        self.assertIn("Too many wrong attempts", message)



    def test_invalid_company_scope_is_rejected_instead_of_becoming_unrestricted(self):
        with self.assertRaisesRegex(ValueError, "Unknown company scope"):
            auth.create_user(
                self.engine,
                "bad-scope@example.test",
                role="operations",
                companies=["NOT-A-COMPANY"],
            )

    def test_invalid_lob_update_is_rejected_without_changing_existing_scope(self):
        with self.assertRaisesRegex(ValueError, "Unknown lob scope"):
            auth.update_user(self.engine, self.user["id"], lobs=["NOT-A-LOB"])
        current = auth.session_user(self.engine, None)
        updated = auth.update_user(self.engine, self.user["id"], lobs=["AE"])
        self.assertEqual(updated["lobs"], ["AE"])

if __name__ == "__main__":
    unittest.main()
