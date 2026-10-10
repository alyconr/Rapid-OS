import tempfile
from pathlib import Path
import unittest
from experiment import StorageExperiment

class TestStorageExperimentSolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_json_storage_execution(self):
        res = StorageExperiment.run_json_storage(self.work_dir, record_count=20)
        self.assertEqual(res["strategy"], "json")
        self.assertEqual(res["records_written"], 20)
        self.assertGreater(res["file_size_bytes"], 0)

    def test_sqlite_storage_execution(self):
        res = StorageExperiment.run_sqlite_storage(self.work_dir, record_count=20)
        self.assertEqual(res["strategy"], "sqlite")
        self.assertEqual(res["records_written"], 20)
        self.assertGreater(res["file_size_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
