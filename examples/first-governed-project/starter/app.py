"""Minimal Task Tracker application."""

class TaskTracker:
    def __init__(self):
        self.tasks: list[dict[str, object]] = []

    def add_task(self, title: str) -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty.")
        task = {
            "id": len(self.tasks) + 1,
            "title": title.strip(),
            "status": "pending",
        }
        self.tasks.append(task)
        return task

    def list_tasks(self) -> list[dict[str, object]]:
        return list(self.tasks)
