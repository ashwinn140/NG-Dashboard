import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, insert, select, update

from app.db import metadata, report_runs, report_schedules, users
from app import report_scheduler_service as service, mailer


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
        self.assertEqual(history[0]["status"], "cancelled")

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

    def test_worker_records_provider_acceptance_and_sends_xlsx_attachment(self):
        schedule = service.create_schedule(self.engine, self.user, self.definition())
        service.queue_manual_run(self.engine, self.user, schedule["id"])
        definition = schedule["definition"]
        prepared = {
            "definition": definition,
            "freshness": {"status": "fresh", "max_age_hours": 48, "imports": [], "missing": []},
            "period_start": date(2026, 11, 2),
            "period_end_exclusive": date(2026, 11, 9),
            "template_context": {
                "report": "Shipment Register", "period_start": "2026-11-02", "period_end": "2026-11-08",
                "date_basis": "Shipment Date", "companies": "NG", "lobs": "AE",
                "row_count": 3, "freshness": "fresh",
            },
            "workbook": {"filename": "shipment_register.xlsx", "content": b"test-xlsx",
                         "row_count": 3, "file_size": 9},
        }
        worker = service.SchedulerWorker(self.engine, store=None)
        with patch.object(service, "prepare_workbook", return_value=prepared) as prepare, patch.object(mailer, "send", return_value=True) as send:
            self.assertTrue(worker.process_one())
        send.assert_called_once()
        sent = send.call_args.kwargs
        self.assertEqual(sent["to"], "owner@example.com")
        self.assertEqual(sent["attachments"][0]["filename"], "shipment_register.xlsx")
        self.assertEqual(sent["attachments"][0]["content"], b"test-xlsx")
        history = service.list_runs(self.engine, self.user["id"], schedule["id"])
        self.assertEqual(history[0]["status"], "provider_accepted")
        self.assertEqual(history[0]["freshness"]["status"], "fresh")

    def test_worker_rechecks_finance_permission_before_generating_jpr(self):
        with self.engine.begin() as conn:
            conn.execute(insert(users).values(
                id=3, email="finance@example.com", user_id="finance", name="Finance",
                role="finance", companies="NG", lobs="AE", finance=1, active=1,
            ))
        finance_user = dict(id=3, email="finance@example.com", name="Finance", role="finance",
                            companies=["NG"], lobs=["AE"], finance=True)
        payload = self.definition()
        payload.update(report_id="job_profitability",
                       columns=["company", "lob", "job_no", "job_date", "income", "expense", "profit", "margin"],
                       sort={"field": "job_date", "direction": "desc"})
        schedule = service.create_schedule(self.engine, finance_user, payload)
        service.queue_manual_run(self.engine, finance_user, schedule["id"])
        with self.engine.begin() as conn:
            conn.execute(update(users).where(users.c.id == 3).values(finance=0))
        worker = service.SchedulerWorker(self.engine, store=None)
        with patch.object(mailer, "send") as send:
            self.assertTrue(worker.process_one())
        send.assert_not_called()
        history = service.list_runs(self.engine, 3, schedule["id"])
        self.assertEqual(history[0]["status"], "failed")
        self.assertEqual(history[0]["error_code"], "permission_revoked")

    def test_mailer_validates_excel_attachment_names(self):
        normalized = mailer._normalize_attachments([{
            "filename": "report.xlsx", "content": b"xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }])
        self.assertEqual(normalized[0]["filename"], "report.xlsx")
        with self.assertRaises(ValueError):
            mailer._normalize_attachments([{"filename": "../private.xlsx", "content": b"x"}])


if __name__ == "__main__":
    unittest.main()
