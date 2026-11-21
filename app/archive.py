"""Safe retention for archived source workbooks on the dashboard volume.

This never deletes imported business rows or import audit metadata. Failed,
held, queued and processing files are retained so they can still be reviewed
or retried.
"""
from datetime import datetime, timedelta
from pathlib import Path
import time

from sqlalchemy import insert, select

from .db import admin_log, imports, uploads


PROTECTED_IMPORT_STATUSES = ("failed", "needs_review")
PROTECTED_UPLOAD_STATUSES = ("queued", "processing", "failed")


def _root(path) -> Path:
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _protected_paths(engine, root: Path) -> set[Path]:
    protected = set()
    with engine.connect() as conn:
        imp_paths = conn.execute(select(imports.c.file_path).where(
            imports.c.status.in_(PROTECTED_IMPORT_STATUSES),
            imports.c.file_path.is_not(None))).scalars().all()
        upload_paths = conn.execute(select(uploads.c.path).where(
            uploads.c.status.in_(PROTECTED_UPLOAD_STATUSES),
            uploads.c.path.is_not(None))).scalars().all()
    for raw in [*imp_paths, *upload_paths]:
        try:
            p = Path(raw).resolve()
            if p.is_relative_to(root):
                protected.add(p)
        except (OSError, TypeError, ValueError):
            continue
    return protected


def _eligible(root: Path, protected: set[Path], cutoff_ts: float):
    for candidate in root.rglob("*"):
        try:
            if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower() != ".xlsx":
                continue
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(root) or resolved in protected:
                continue
            stat = candidate.stat()
            if stat.st_mtime < cutoff_ts:
                yield candidate, stat.st_size
        except OSError:
            continue


def archive_preview(engine, upload_dir, days: int = 90, now: datetime | None = None) -> dict:
    days = max(30, min(3650, int(days)))
    now = now or datetime.utcnow()
    root = _root(upload_dir)
    protected = _protected_paths(engine, root)
    cutoff_ts = now.timestamp() - days * 86400
    files = list(_eligible(root, protected, cutoff_ts))
    total = sum(size for _, size in files)
    return {
        "retention_days": days,
        "cutoff_utc": (now - timedelta(days=days)).isoformat() + "Z",
        "eligible_files": len(files),
        "eligible_bytes": total,
        "protected_files": len(protected),
        "sample": [p.name for p, _ in files[:20]],
    }


def archive_apply(engine, upload_dir, approved_by: str, reason: str,
                  days: int = 90, now: datetime | None = None) -> dict:
    if not str(reason or "").strip():
        raise ValueError("A reason is required.")
    days = max(30, min(3650, int(days)))
    now = now or datetime.utcnow()
    root = _root(upload_dir)
    protected = _protected_paths(engine, root)
    cutoff_ts = now.timestamp() - days * 86400
    removed_files = removed_bytes = 0
    for path, size in list(_eligible(root, protected, cutoff_ts)):
        try:
            path.unlink()
            removed_files += 1
            removed_bytes += size
        except FileNotFoundError:
            continue
    with engine.begin() as conn:
        conn.execute(insert(admin_log).values(
            at=now, user=approved_by, action="archive_retention",
            detail=f"Removed {removed_files} archived source workbook(s) ({removed_bytes} bytes) older than {days} days. Reason: {reason}"))
    return {"status": "done", "removed_files": removed_files, "removed_bytes": removed_bytes,
            "retention_days": days, "reason": reason}
