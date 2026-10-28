from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class ActionKind(str, Enum):
    AUTHOR_SPEC = "author_spec"
    RUN_BASELINE = "run_baseline"
    ACTIVATE = "activate"
    IMPLEMENT_TASK = "implement_task"
    VERIFY = "verify"
    AWAIT_HUMAN_APPROVAL = "await_human_approval"
    FINISH = "finish"
    DONE = "done"
    BLOCKED = "blocked"

    @classmethod
    def coerce(cls, value: object) -> "ActionKind":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise ValueError(
            f"Invalid ActionKind '{value}': expected one of {[m.value for m in cls]}."
        )


@dataclass(frozen=True)
class NextAction:
    schema_version: int = 1
    run_id: str | None = None
    mode: str | None = None
    kind: ActionKind | str = ActionKind.AUTHOR_SPEC
    instructions: str = ""
    task_id: str | None = None
    gate_ids: tuple[str, ...] = ()
    command: list[str] | None = None
    after: list[str] | None = None
    awaiting_human: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    tasks_done: int = 0
    tasks_total: int = 0
    outcome: str | None = None
    spec_template: dict[str, object] | None = None
    workspace_path: str | None = None
    # `author_spec` only: the open stories of the product brief (see adapters/project_docs.py).
    seed: dict[str, object] | None = None
    # Facts about this start the person should know (for example a renumbered task list).
    notes: tuple[str, ...] = ()
    # `blocked` by a rejected human review: who rejected which gates and why (the `--reason` text).
    rejection: dict[str, object] | None = None

    def __post_init__(self):
        coerced_kind = ActionKind.coerce(self.kind)
        object.__setattr__(self, "kind", coerced_kind)
        if isinstance(self.gate_ids, (list, set)):
            object.__setattr__(self, "gate_ids", tuple(self.gate_ids))
        if self.command is not None:
            object.__setattr__(self, "command", list(self.command))
        if self.after is not None:
            object.__setattr__(self, "after", list(self.after))
        if isinstance(self.awaiting_human, (list, set)):
            object.__setattr__(self, "awaiting_human", tuple(sorted(self.awaiting_human)))
        if isinstance(self.missing, (list, set)):
            object.__setattr__(self, "missing", tuple(sorted(self.missing)))

    @property
    def action(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": self.kind.value,
        }
        if self.task_id is not None:
            payload["task_id"] = self.task_id
        if self.gate_ids:
            payload["gate_ids"] = list(self.gate_ids)
        payload["instructions"] = self.instructions
        payload["command"] = list(self.command) if self.command is not None else None
        payload["after"] = list(self.after) if self.after is not None else None
        if self.spec_template is not None:
            payload["spec_template"] = dict(self.spec_template)
        if self.workspace_path is not None:
            payload["workspace_path"] = self.workspace_path
        if self.seed is not None:
            payload["seed"] = dict(self.seed)
        if self.rejection is not None:
            payload["rejection"] = dict(self.rejection)
        return payload

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "mode": self.mode,
            "action": self.action,
            "awaiting_human": list(self.awaiting_human),
            "missing": list(self.missing),
            "progress": {
                "tasks_done": self.tasks_done,
                "tasks_total": self.tasks_total,
            },
            "outcome": self.outcome if self.kind == ActionKind.DONE else None,
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload
