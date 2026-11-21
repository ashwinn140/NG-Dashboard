import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine

from app.db import metadata
from app.server import Store


class ImportWorkerWarmupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.tmp.name) / "worker.db"), future=True)
        metadata.create_all(self.engine)
        self.store = Store(self.engine, str(Path(self.tmp.name) / "uploads"), start_worker=False)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def queue_one(self):
        self.store.enqueue(file_name="daily.xlsx", path="unused.xlsx", source="email",
                           subject="", sender="", gmail_id="", report_time=None,
                           uploaded_by="")

    def test_successful_promotion_warms_once_after_queue_drains(self):
        self.queue_one()
        warm_calls = []
        def warm():
            warm_calls.append(True)
            self.store.stop = True
            return True
        with patch("app.server.P.ingest_file", return_value={"status": "promoted"}), patch.object(self.store, "warm", side_effect=warm):
            self.store._worker()
        self.assertEqual(len(warm_calls), 1)
        self.assertFalse(self.store.needs_warm)

    def test_duplicate_does_not_trigger_full_dataset_warmup(self):
        self.queue_one()
        warm_calls = []
        def ingest(*args, **kwargs):
            self.store.stop = True
            return {"status": "duplicate"}
        with patch("app.server.P.ingest_file", side_effect=ingest), patch.object(self.store, "warm", side_effect=lambda: warm_calls.append(True)):
            self.store._worker()
        self.assertEqual(warm_calls, [])
        self.assertFalse(self.store.needs_warm)


if __name__ == "__main__":
    unittest.main()
