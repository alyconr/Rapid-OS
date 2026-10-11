"""Enhanced Task Tracker application with priority support."""

class TaskTracker:
    VALID_PRIORITIES = ("low", "medium", "high")

    def __init__(self):
        self.tasks: list[dict[str, object]] = []

    def add_task(self, title: str, priority: str = "medium") -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty.")
        priority_normalized = priority.lower().strip()
        if priority_normalized not in self.VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}': must be one of {self.VALID_PRIORITIES}.")
        task = {
            "id": len(self.tasks) + 1,
            "title": title.strip(),
            "priority": priority_normalized,
            "status": "pending",
        }
        self.tasks.append(task)
        return task

    def list_tasks(self, priority: str | None = None) -> list[dict[str, object]]:
        if priority is None:
            return list(self.tasks)
        p = priority.lower().strip()
        return [t for t in self.tasks if t["priority"] == p]
