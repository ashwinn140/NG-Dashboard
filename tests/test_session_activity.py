import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select

from app import auth
from app.db import metadata, session_activity, sessions


class SessionActivityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        self.user = auth.create_user(self.engine, "activity@example.test", role="admin")
        self.now = datetime(2026, 11, 21, 9, 0, 0)
        self.raw, _ = auth.create_session(self.engine, self.user["id"], "password", self.now)

    def tearDown(self):
        self.engine.dispose()

    def activity_row(self):
        with self.engine.connect() as conn:
            return conn.execute(select(session_activity)).mappings().one_or_none()

    def test_records_and_throttles_activity_without_extending_session(self):
        self.assertTrue(auth.record_activity(self.engine, self.raw, self.user["id"], self.now))
        first = self.activity_row()
        self.assertEqual(first["last_activity_at"], self.now)
        self.assertTrue(auth.record_activity(self.engine, self.raw, self.user["id"], self.now + timedelta(seconds=30)))
        self.assertEqual(self.activity_row()["last_activity_at"], self.now)
        later = self.now + timedelta(seconds=121)
        self.assertTrue(auth.record_activity(self.engine, self.raw, self.user["id"], later))
        self.assertEqual(self.activity_row()["last_activity_at"], later)
        with self.engine.connect() as conn:
            expiry = conn.execute(select(sessions.c.expires_at)).scalar_one()
        self.assertEqual(expiry, self.now + timedelta(hours=auth.SESSION_HOURS))

    def test_expired_session_cannot_write_activity(self):
        expired = self.now + timedelta(hours=auth.SESSION_HOURS, seconds=1)
        self.assertFalse(auth.record_activity(self.engine, self.raw, self.user["id"], expired))
        self.assertIsNone(self.activity_row())

    def test_logout_removes_activity_record(self):
        auth.record_activity(self.engine, self.raw, self.user["id"], self.now)
        auth.end_session(self.engine, self.raw)
        self.assertIsNone(self.activity_row())

    def test_deactivating_user_removes_sessions_and_activity(self):
        auth.record_activity(self.engine, self.raw, self.user["id"], self.now)
        auth.update_user(self.engine, self.user["id"], active=False)
        self.assertIsNone(self.activity_row())
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(select(sessions.c.id)).all(), [])


if __name__ == "__main__":
    unittest.main()
