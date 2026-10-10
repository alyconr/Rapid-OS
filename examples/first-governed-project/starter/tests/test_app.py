import unittest
from app import TaskTracker

class TestTaskTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = TaskTracker()

    def test_add_and_list_tasks(self):
        task = self.tracker.add_task("Initial task")
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["title"], "Initial task")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(len(self.tracker.list_tasks()), 1)

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("")

if __name__ == "__main__":
    unittest.main()
