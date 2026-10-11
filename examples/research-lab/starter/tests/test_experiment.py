import unittest
from experiment import StorageExperiment

class TestStorageExperimentBaseline(unittest.TestCase):
    def test_stub_state(self):
        exp = StorageExperiment()
        res = exp.run_benchmark()
        self.assertEqual(res["status"], "unimplemented")

if __name__ == "__main__":
    unittest.main()
