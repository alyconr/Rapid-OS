import unittest
from app import TaskTracker

class TestTaskTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = TaskTracker()

    def test_add_and_list_tasks_default_priority(self):
        task = self.tracker.add_task("Initial task")
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["title"], "Initial task")
        self.assertEqual(task["priority"], "medium")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(len(self.tracker.list_tasks()), 1)

    def test_add_task_with_custom_priority(self):
        t1 = self.tracker.add_task("Urgent bug", priority="high")
        t2 = self.tracker.add_task("Clean backlog", priority="low")
        self.assertEqual(t1["priority"], "high")
        self.assertEqual(t2["priority"], "low")
        high_tasks = self.tracker.list_tasks(priority="high")
        self.assertEqual(len(high_tasks), 1)
        self.assertEqual(high_tasks[0]["title"], "Urgent bug")

    def test_reject_invalid_priority(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("Invalid", priority="critical")

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("")

if __name__ == "__main__":
    unittest.main()
