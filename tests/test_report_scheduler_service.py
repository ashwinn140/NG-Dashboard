import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, insert, select, update

from app.db import metadata, report_runs, report_schedules, users
from app import report_scheduler_service as service


class SchedulerServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(insert(users), [
                dict(id=1, email="owner@example.com", user_id="owner", name="Owner", role="operations",
                     companies="NG", lobs="AE", finance=0, active=1),
                dict(id=2, email="other@example.com", user_id="other", name="Other", role="operations",
                     companies="NG", lobs="AE", finance=0, active=1),
            ])
        self.user = dict(id=1, email="owner@example.com", name="Owner", role="operations",
                         companies=["NG"], lobs=["AE"], finance=False)

    def tearDown(self):
        self.engine.dispose()

    def definition(self):
        return {
            "report_id": "shipment_register",
            "companies": ["NG"],
            "lobs": ["AE"],
            "frequency": "weekly",
            "timezone": "Asia/Kolkata",
            "run_at_local": "08:00",
            "weekday": 0,
            "period": "last_7_completed_days",
            "summary_detail": "detail",
            "columns": ["company", "shipment_no", "shipment_date"],
            "sort": {"field": "shipment_date", "direction": "desc"},
            "filters": {},
            "freshness_policy": {"action": "skip", "max_age_hours": 48},
            "recipients": ["self"],
        }

    def test_create_paused_schedule_and_reject_other_owner(self):
        schedule = service.create_schedule(self.engine, self.user, self.definition())
        self.assertEqual(schedule["status"], "paused")
        self.assertEqual(schedule["report_id"], "shipment_register")
        with self.assertRaises(KeyError):
            service.get_schedule(self.engine, 2, schedule["id"])

    def test_resume_pause_and_soft_deactivate_preserve_run_history(self):
        schedule = service.create_schedule(self.engine, self.user, self.definition())
        active = service.update_schedule(self.engine, self.user, schedule["id"], {"status": "active"})
        self.assertEqual(active["status"], "active")
        paused = service.update_schedule(self.engine, self.user, schedule["id"], {"status": "paused"})
        self.assertEqual(paused["status"], "paused")
        with patch.dict(os.environ, {"REPORT_SCHEDULER_ENABLED": "false"}):
            queued = service.queue_manual_run(self.engine, self.user, schedule["id"])
        self.assertEqual(queued["status"], "queued")
        self.assertFalse(queued["worker_enabled"])
        deactivated = service.delete_schedule(self.engine, self.user, schedule["id"])
        self.assertEqual(deactivated["status"], "disabled")
        self.assertEqual(service.list_schedules(self.engine, self.user["id"]), [])
        history = service.list_runs(self.engine, self.user["id"], schedule["id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "queued")

    def test_due_schedule_enqueue_is_idempotent(self):
        schedule = service.create_schedule(self.engine, self.user, self.definition())
        service.update_schedule(self.engine, self.user, schedule["id"], {"status": "active"})
        due = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        with self.engine.begin() as conn:
            conn.execute(update(report_schedules).where(
                report_schedules.c.id == schedule["id"]
            ).values(next_run_at=due))
        self.assertEqual(service.enqueue_due_schedules(self.engine), 1)
        self.assertEqual(service.enqueue_due_schedules(self.engine), 0)
        with self.engine.connect() as conn:
            runs = conn.execute(select(report_runs).where(
                report_runs.c.schedule_id == schedule["id"]
            )).all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, "queued")

    def test_template_attribute_access_is_rejected(self):
        payload = self.definition()
        payload["email_subject"] = "{report.__class__}"
        with self.assertRaises(service.ScheduleValidationError):
            service.create_schedule(self.engine, self.user, payload)

    def test_freshness_reports_missing_source_imports(self):
        result = service._freshness(
            self.engine, self.definition(), datetime.now(timezone.utc).replace(tzinfo=None), 48
        )
        self.assertEqual(result["status"], "missing")
        self.assertIn("NG/AE", result["missing"])


if __name__ == "__main__":
    unittest.main()
