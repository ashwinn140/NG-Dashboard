"""Persistent, permission-aware report schedule service and opt-in worker."""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import auth, admin_ops as ops, mailer
from .db import admin_log, imports, report_runs, report_schedules, users
from .report_scheduler import (
    PERIODS, REPORT_CATALOG, ScheduleValidationError, build_report_workbook,
    next_run_at, period_bounds, validate_schedule,
)

log = logging.getLogger("report_scheduler")
UTC = timezone.utc
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ALLOWED_TEMPLATE_KEYS = {
    "report", "period_start", "period_end", "date_basis", "companies", "lobs",
    "row_count", "freshness",
}
DEFAULT_SUBJECT = "{report} · {period_start} to {period_end}"
DEFAULT_MESSAGE = (
    "Please find the requested report attached.\n\n"
    "Period: {period_start} to {period_end}\n"
    "Date basis: {date_basis}\n"
    "Companies: {companies} · LOBs: {lobs}\n"
    "Rows: {row_count}\n"
    "Data freshness: {freshness}\n"
)


def _now() -> datetime:
    """UTC, naive: all production DateTime columns are stored as UTC-naive."""
    return datetime.now(UTC).replace(tzinfo=None)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _audit(engine, email: str, action: str, detail: str = "") -> None:
    try:
        with engine.begin() as conn:
            conn.execute(insert(admin_log).values(
                at=_now(), user=email, action=action, detail=str(detail)[:2000]
            ))
    except Exception:
        log.exception("Could not write scheduler audit event")


def _definition_user(engine, owner_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(users).where(users.c.id == owner_id, users.c.active == 1)
        ).first()
    return auth.user_dict(row) if row else None


def _report_definition(user: dict, payload: dict) -> dict:
    normalized = validate_schedule(user, payload)
    subject = str(payload.get("email_subject") or DEFAULT_SUBJECT).strip()
    message = str(payload.get("email_message") or DEFAULT_MESSAGE).strip()
    if not subject or len(subject) > 180 or "\r" in subject or "\n" in subject:
        raise ScheduleValidationError("Email subject must be 1–180 characters on one line.")
    if not message or len(message) > 4000:
        raise ScheduleValidationError("Email message must be 1–4,000 characters.")
    for template in (subject, message):
        # Reject unknown or malformed replacement fields when the schedule is saved.
        try:
            keys = {field.split(".", 1)[0].split("[", 1)[0] for _, field, _, _ in __import__("string").Formatter().parse(template) if field}
        except ValueError as exc:
            raise ScheduleValidationError("Email subject or message has invalid template syntax.") from exc
        if not keys.issubset(ALLOWED_TEMPLATE_KEYS):
            raise ScheduleValidationError("Email templates may use only: " + ", ".join(sorted(ALLOWED_TEMPLATE_KEYS)))
    normalized["email_subject"] = subject
    normalized["email_message"] = message
    return normalized


def _next_for(definition: dict, now: datetime | None = None) -> datetime:
    now = now or _now()
    return next_run_at(
        _aware(now), definition["frequency"], definition["timezone"],
        definition["run_at_local"], definition.get("weekday"), definition.get("monthday"),
    ).replace(tzinfo=None)


def create_schedule(engine, user: dict, payload: dict) -> dict:
    definition = _report_definition(user, payload)
    now = _now()
    next_at = _next_for(definition, now)
    with engine.begin() as conn:
        result = conn.execute(insert(report_schedules).values(
            owner_id=user["id"], report_id=definition["report_id"],
            report_version=definition["report_version"], definition=definition,
            status="paused", next_run_at=next_at, created_at=now, updated_at=now,
        ))
        schedule_id = result.inserted_primary_key[0]
    _audit(engine, user["email"], "report_schedule_created",
           f"Schedule {schedule_id}: {definition['report_id']}; starts paused")
    return get_schedule(engine, user["id"], schedule_id)


def get_schedule(engine, owner_id: int, schedule_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(select(report_schedules).where(
            report_schedules.c.id == schedule_id,
            report_schedules.c.owner_id == owner_id,
        )).mappings().first()
    if not row:
        raise KeyError("Schedule not found.")
    return _schedule_json(row)


def _schedule_json(row) -> dict:
    definition = row["definition"] or {}
    return {
        "id": row["id"], "report_id": row["report_id"],
        "report_title": REPORT_CATALOG.get(row["report_id"], {}).get("title", row["report_id"]),
        "definition": definition, "status": row["status"],
        "next_run_at": row["next_run_at"].isoformat() + "Z" if row["next_run_at"] else None,
        "last_run_at": row["last_run_at"].isoformat() + "Z" if row["last_run_at"] else None,
        "last_error": row["last_error"] or "",
        "created_at": row["created_at"].isoformat() + "Z" if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() + "Z" if row["updated_at"] else None,
    }


def list_schedules(engine, owner_id: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(report_schedules).where(
            report_schedules.c.owner_id == owner_id,
            report_schedules.c.status != "disabled",
        ).order_by(report_schedules.c.created_at.desc())).mappings().all()
    return [_schedule_json(row) for row in rows]


def update_schedule(engine, user: dict, schedule_id: int, payload: dict) -> dict:
    current = get_schedule(engine, user["id"], schedule_id)
    now = _now()
    values = {"updated_at": now}
    definition = current["definition"]
    if "definition" in payload:
        definition = _report_definition(user, payload["definition"])
        values.update(definition=definition, report_id=definition["report_id"],
                      report_version=definition["report_version"], next_run_at=_next_for(definition, now))
    status = payload.get("status")
    if status is not None:
        if status not in ("active", "paused", "disabled"):
            raise ScheduleValidationError("Schedule status must be active or paused.")
        values["status"] = status
        if status == "active" and not values.get("next_run_at"):
            values["next_run_at"] = _next_for(definition, now)
    with engine.begin() as conn:
        result = conn.execute(update(report_schedules).where(
            report_schedules.c.id == schedule_id,
            report_schedules.c.owner_id == user["id"],
            report_schedules.c.status != "disabled",
        ).values(**values))
        if result.rowcount != 1:
            raise KeyError("Schedule not found.")
        if status == "disabled":
            conn.execute(update(report_runs).where(
                report_runs.c.schedule_id == schedule_id,
                report_runs.c.status.in_(("queued", "retry_wait")),
            ).values(status="cancelled", finished_at=now, error_code="schedule_disabled",
                     error_message="Schedule was deactivated."))
    action = "report_schedule_" + (status or "updated")
    _audit(engine, user["email"], action, f"Schedule {schedule_id}")
    return get_schedule(engine, user["id"], schedule_id)


def delete_schedule(engine, user: dict, schedule_id: int) -> dict:
    # Soft-disable: preserve run history and the unique idempotency record.
    return update_schedule(engine, user, schedule_id, {"status": "disabled"})


def list_runs(engine, owner_id: int, schedule_id: int, limit: int = 50) -> list[dict]:
    get_schedule(engine, owner_id, schedule_id)  # owner check
    limit = max(1, min(int(limit), 100))
    with engine.connect() as conn:
        rows = conn.execute(
            select(report_runs).where(report_runs.c.schedule_id == schedule_id)
            .order_by(report_runs.c.created_at.desc()).limit(limit)
        ).mappings().all()
    return [{
        "id": r["id"], "scheduled_for": r["scheduled_for"].isoformat() + "Z",
        "status": r["status"], "attempts": r["attempts"],
        "period_start": r["period_start"].isoformat() if r["period_start"] else None,
        "period_end": (r["period_end_exclusive"] - timedelta(days=1)).isoformat() if r["period_end_exclusive"] else None,
        "freshness": r["freshness"], "row_count": r["row_count"], "file_size": r["file_size"],
        "provider_status": r["provider_status"], "error_code": r["error_code"],
        "error_message": r["error_message"], "started_at": r["started_at"].isoformat() + "Z" if r["started_at"] else None,
        "finished_at": r["finished_at"].isoformat() + "Z" if r["finished_at"] else None,
    } for r in rows]


def queue_manual_run(engine, user: dict, schedule_id: int) -> dict:
    schedule = get_schedule(engine, user["id"], schedule_id)
    now = _now()
    definition = schedule["definition"]
    key = f"manual:{schedule_id}:{now.isoformat(timespec='microseconds')}:{definition['report_version']}"
    with engine.begin() as conn:
        result = conn.execute(insert(report_runs).values(
            schedule_id=schedule_id, scheduled_for=now, idempotency_key=key,
            status="queued", attempts=0, created_at=now,
        ))
        run_id = result.inserted_primary_key[0]
    _audit(engine, user["email"], "report_schedule_run_now", f"Schedule {schedule_id}; run {run_id}")
    return {"run_id": run_id, "status": "queued", "worker_enabled": _worker_enabled()}


def _worker_enabled() -> bool:
    return str(__import__("os").environ.get("REPORT_SCHEDULER_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")


def _freshness(engine, definition: dict, now: datetime, max_age_hours: int) -> dict:
    expected = []
    if definition["report_id"] == "job_profitability":
        expected = [(company, "JP") for company in definition["companies"]]
    else:
        expected = [(company, lob) for company in definition["companies"] for lob in definition["lobs"]]
    found = []
    missing = []
    for company, report_type in expected:
        with engine.connect() as conn:
            row = conn.execute(select(imports.c.id, imports.c.report_time, imports.c.received_at).where(
                imports.c.company == company, imports.c.report_type == report_type,
                imports.c.status == "promoted",
            ).order_by(imports.c.id.desc()).limit(1)).first()
        if not row:
            missing.append(f"{company}/{report_type}")
            continue
        stamp = row.report_time or row.received_at
        if not stamp:
            missing.append(f"{company}/{report_type}")
            continue
        age = max(0.0, (now - stamp).total_seconds() / 3600)
        found.append({"company": company, "report_type": report_type, "import_id": row.id,
                      "as_of": stamp.isoformat() + "Z", "age_hours": round(age, 2)})
    worst = max((item["age_hours"] for item in found), default=None)
    stale = bool(missing) or worst is None or worst > max_age_hours
    return {"status": "missing" if missing else "stale" if stale else "fresh",
            "max_age_hours": max_age_hours, "worst_age_hours": worst,
            "imports": found, "missing": missing}


def prepare_workbook(engine, store, user: dict, definition: dict, now: datetime | None = None) -> dict:
    """Re-check permissions, source coverage and build the same XLSX for preview or execution."""
    now = now or _now()
    current_user = _definition_user(engine, user["id"])
    if not current_user:
        raise PermissionError("The schedule owner is inactive or no longer exists.")
    # Revalidate stored company/LOB/finance scope against today's account permissions.
    normalized = _report_definition(current_user, definition)
    settings = ops.get_settings(engine)
    zone = ZoneInfo(normalized["timezone"])
    local_now = _aware(now).astimezone(zone)
    period_start, period_end = period_bounds(
        normalized["period"], local_now.date(), int(settings["fy_start_month"]),
        normalized.get("start_date"), normalized.get("end_date"),
    )
    freshness_policy = normalized["freshness_policy"]
    freshness = _freshness(engine, normalized, now, int(freshness_policy["max_age_hours"]))
    data = json.loads(gzip.decompress(store.dataset_for(current_user)))
    if data.get("empty"):
        raise ScheduleValidationError("No dashboard data has been loaded yet.")
    workbook = build_report_workbook(data, normalized, period_start, period_end, freshness,
                                     generated_at=_aware(now))
    context = {
        "report": REPORT_CATALOG[normalized["report_id"]]["title"],
        "period_start": period_start.isoformat(), "period_end": (period_end - timedelta(days=1)).isoformat(),
        "date_basis": normalized["date_basis"], "companies": ", ".join(normalized["companies"]),
        "lobs": ", ".join(normalized["lobs"]), "row_count": workbook["row_count"],
        "freshness": freshness["status"],
    }
    return {"workbook": workbook, "definition": normalized, "freshness": freshness,
            "period_start": period_start, "period_end_exclusive": period_end,
            "template_context": context, "owner": current_user}


def preview_workbook(engine, store, user: dict, payload: dict) -> dict:
    definition = _report_definition(user, payload)
    return prepare_workbook(engine, store, user, definition)


def enqueue_due_schedules(engine, now: datetime | None = None) -> int:
    now = now or _now()
    with engine.connect() as conn:
        due = conn.execute(select(report_schedules).where(
            report_schedules.c.status == "active",
            report_schedules.c.next_run_at.is_not(None),
            report_schedules.c.next_run_at <= now,
        ).order_by(report_schedules.c.next_run_at).limit(100)).mappings().all()
    created = 0
    for schedule in due:
        scheduled_for = schedule["next_run_at"]
        definition = schedule["definition"]
        next_at = _next_for(definition, scheduled_for)
        key = f"schedule:{schedule['id']}:{scheduled_for.isoformat()}:{schedule['report_version']}"
        try:
            with engine.begin() as conn:
                claimed = conn.execute(update(report_schedules).where(
                    report_schedules.c.id == schedule["id"],
                    report_schedules.c.status == "active",
                    report_schedules.c.next_run_at == scheduled_for,
                ).values(next_run_at=next_at, updated_at=now))
                if claimed.rowcount != 1:
                    continue
                conn.execute(insert(report_runs).values(
                    schedule_id=schedule["id"], scheduled_for=scheduled_for,
                    idempotency_key=key, status="queued", attempts=0, created_at=now,
                ))
            created += 1
        except IntegrityError:
            # A duplicate schedule/instant is harmless; the unique constraints are the final arbiter.
            continue
        except Exception:
            log.exception("Could not enqueue schedule %s", schedule["id"])
    return created


class SchedulerWorker:
    """Opt-in polling worker. No delivery begins unless REPORT_SCHEDULER_ENABLED=true."""
    def __init__(self, engine, store, poll_seconds: int = 5):
        self.engine, self.store, self.poll_seconds = engine, store, max(2, int(poll_seconds))
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not _worker_enabled():
            log.info("Report scheduler worker is disabled; no scheduled email will be sent.")
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="report-scheduler")
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def _run(self):
        self._recover_abandoned()
        while not self._stop.is_set():
            try:
                enqueue_due_schedules(self.engine)
                worked = self.process_one()
                if not worked:
                    self._stop.wait(self.poll_seconds)
            except Exception:
                log.exception("Report scheduler loop failed")
                self._stop.wait(self.poll_seconds)

    def _recover_abandoned(self):
        cutoff = _now() - timedelta(minutes=30)
        with self.engine.begin() as conn:
            conn.execute(update(report_runs).where(
                report_runs.c.status == "generating",
                report_runs.c.started_at < cutoff,
            ).values(status="retry_wait", retry_after=_now(), error_code="worker_interrupted",
                     error_message="Worker interrupted during report generation; safely retrying."))

    def process_one(self) -> bool:
        now = _now()
        with self.engine.begin() as conn:
            candidate = conn.execute(select(report_runs).where(
                (report_runs.c.status == "queued") |
                and_(report_runs.c.status == "retry_wait", report_runs.c.retry_after <= now),
            ).order_by(report_runs.c.created_at).limit(1)).mappings().first()
            if not candidate:
                return False
            claimed = conn.execute(update(report_runs).where(
                report_runs.c.id == candidate["id"],
                report_runs.c.status == candidate["status"],
            ).values(status="generating", attempts=report_runs.c.attempts + 1,
                     started_at=now, retry_after=None))
            if claimed.rowcount != 1:
                return False
        self._execute_run(candidate["id"])
        return True

    def _finish(self, run_id: int, **values):
        values.setdefault("finished_at", _now())
        with self.engine.begin() as conn:
            conn.execute(update(report_runs).where(report_runs.c.id == run_id).values(**values))

    def _execute_run(self, run_id: int):
        with self.engine.connect() as conn:
            run = conn.execute(select(report_runs).where(report_runs.c.id == run_id)).mappings().first()
            schedule = conn.execute(select(report_schedules).where(
                report_schedules.c.id == run["schedule_id"]
            )).mappings().first() if run else None
        if not run or not schedule:
            self._finish(run_id, status="failed", error_code="schedule_missing",
                         error_message="Schedule was removed before the run started.")
            return
        owner = _definition_user(self.engine, schedule["owner_id"])
        if not owner:
            self._finish(run_id, status="failed", error_code="owner_inactive",
                         error_message="Schedule owner is inactive or no longer exists.")
            return
        try:
            prepared = prepare_workbook(self.engine, self.store, owner, schedule["definition"])
            freshness = prepared["freshness"]
            policy = prepared["definition"]["freshness_policy"]
            if freshness["status"] != "fresh":
                if policy["action"] == "skip":
                    self._finish(run_id, status="skipped_stale", freshness=freshness,
                                 period_start=prepared["period_start"],
                                 period_end_exclusive=prepared["period_end_exclusive"],
                                 error_code="source_data_stale",
                                 error_message="Source data is missing or older than the configured freshness limit.")
                    _audit(self.engine, owner["email"], "report_schedule_skipped_stale",
                           f"Schedule {schedule['id']}; run {run_id}")
                    return
                if policy["action"] == "delay":
                    deadline = run["created_at"] + timedelta(hours=int(policy.get("max_delay_hours", 24)))
                    now = _now()
                    if now < deadline:
                        retry_at = min(deadline, now + timedelta(hours=1))
                        self._finish(run_id, status="retry_wait", retry_after=retry_at,
                                     freshness=freshness, finished_at=None,
                                     error_code="waiting_for_fresh_data",
                                     error_message="Source data is not fresh yet; waiting within the configured delay window.")
                    else:
                        self._finish(run_id, status="skipped_stale", freshness=freshness,
                                     error_code="freshness_delay_expired",
                                     error_message="Freshness delay window expired; the report was not sent.")
                    return
            owner_email = owner["email"].strip().lower()
            context = prepared["template_context"]
            subject = prepared["definition"]["email_subject"].format_map(context)[:180]
            body = prepared["definition"]["email_message"].format_map(context)
            sent = mailer.send(owner_email, subject, body, attachments=[{
                "filename": prepared["workbook"]["filename"],
                "content": prepared["workbook"]["content"], "content_type": XLSX_MIME,
            }])
            if not sent:
                attempts = run["attempts"] + 1
                if attempts < 3:
                    self._finish(run_id, status="retry_wait",
                                 retry_after=_now() + timedelta(minutes=5 * (2 ** (attempts - 1))),
                                 freshness=freshness, row_count=prepared["workbook"]["row_count"],
                                 file_size=prepared["workbook"]["file_size"],
                                 error_code="email_provider_rejected",
                                 error_message="Email provider did not accept the submission; retry scheduled.")
                else:
                    self._finish(run_id, status="failed", freshness=freshness,
                                 row_count=prepared["workbook"]["row_count"],
                                 file_size=prepared["workbook"]["file_size"],
                                 error_code="email_provider_rejected",
                                 error_message="Email provider did not accept the submission after 3 attempts.")
                return
            digest = hashlib.sha256(prepared["workbook"]["content"]).hexdigest()
            self._finish(run_id, status="provider_accepted", freshness=freshness,
                         period_start=prepared["period_start"],
                         period_end_exclusive=prepared["period_end_exclusive"],
                         row_count=prepared["workbook"]["row_count"],
                         file_size=prepared["workbook"]["file_size"], file_sha256=digest,
                         provider_status="accepted", error_code=None, error_message=None)
            with self.engine.begin() as conn:
                conn.execute(update(report_schedules).where(
                    report_schedules.c.id == schedule["id"]
                ).values(last_run_at=_now(), last_error=None, updated_at=_now()))
            _audit(self.engine, owner_email, "report_schedule_provider_accepted",
                   f"Schedule {schedule['id']}; run {run_id}; provider submission accepted")
        except PermissionError as exc:
            self._finish(run_id, status="failed", error_code="permission_revoked",
                         error_message=str(exc)[:1000])
        except (ScheduleValidationError, ValueError, TypeError, KeyError) as exc:
            self._finish(run_id, status="failed", error_code="report_validation_failed",
                         error_message=str(exc)[:1000])
        except Exception as exc:
            log.exception("Scheduled report run %s failed", run_id)
            attempts = run["attempts"] + 1
            if attempts < 3:
                self._finish(run_id, status="retry_wait",
                             retry_after=_now() + timedelta(minutes=5 * (2 ** (attempts - 1))),
                             error_code=type(exc).__name__,
                             error_message="Unexpected report failure; retry scheduled.")
            else:
                self._finish(run_id, status="failed", error_code=type(exc).__name__,
                             error_message="Unexpected report failure after 3 attempts.")
