import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, insert, select, func

from app.archive import archive_preview, archive_apply
from app.db import metadata, imports, uploads, admin_log


class ArchiveRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "uploads"
        self.root.mkdir()
        self.engine = create_engine("sqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        self.now = datetime(2026, 11, 21, 9, 0, 0)

        self.old_promoted = self.root / "old-promoted.xlsx"
        self.old_failed = self.root / "old-failed.xlsx"
        self.recent = self.root / "recent.xlsx"
        self.other = self.root / "old-other.txt"
        for path in (self.old_promoted, self.old_failed, self.recent, self.other):
            path.write_bytes(b"source workbook")
        os.utime(self.old_promoted, (self.now.timestamp() - 120 * 86400,) * 2)
        os.utime(self.old_failed, (self.now.timestamp() - 120 * 86400,) * 2)
        os.utime(self.recent, (self.now.timestamp() - 10 * 86400,) * 2)
        os.utime(self.other, (self.now.timestamp() - 120 * 86400,) * 2)

        with self.engine.begin() as conn:
            conn.execute(insert(imports), [
                {"file_name": "old-promoted.xlsx", "file_path": str(self.old_promoted), "status": "promoted"},
                {"file_name": "old-failed.xlsx", "file_path": str(self.old_failed), "status": "failed"},
                {"file_name": "recent.xlsx", "file_path": str(self.recent), "status": "promoted"},
            ])
            conn.execute(insert(uploads), [
                {"file_name": "old-failed.xlsx", "path": str(self.old_failed), "status": "failed"},
            ])

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def test_preview_excludes_recent_and_retryable_source_files(self):
        result = archive_preview(self.engine, self.root, days=90, now=self.now)
        self.assertEqual(result["archive_files_total"], 3)
        self.assertEqual(result["eligible_files"], 1)
        self.assertEqual(result["sample"], ["old-promoted.xlsx"])
        self.assertGreater(result["eligible_bytes"], 0)

    def test_apply_deletes_only_expired_unprotected_files_and_keeps_audit_rows(self):
        result = archive_apply(self.engine, self.root, "admin@example.test", "approved test cleanup",
                               days=90, now=self.now)
        self.assertEqual(result["removed_files"], 1)
        self.assertFalse(self.old_promoted.exists())
        self.assertTrue(self.old_failed.exists())
        self.assertTrue(self.recent.exists())
        self.assertTrue(self.other.exists())
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(select(func.count()).select_from(imports)).scalar(), 3)
            self.assertEqual(conn.execute(select(func.count()).select_from(admin_log)).scalar(), 1)


if __name__ == "__main__":
    unittest.main()
