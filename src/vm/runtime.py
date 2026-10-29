"""Runtime objects: frames, semaphores, condition variables, monitors, processes."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


class Frame:
    """A lexical scope.  Function frames chain to the global frame."""

    __slots__ = ("vars", "parent")

    def __init__(self, parent: "Frame | None" = None) -> None:
        self.vars: dict[str, Any] = {}
        self.parent = parent


class Semaphore:
    def __init__(self, name: str, value: int = 0) -> None:
        self.name = name
        self.value = value
        self.waiters: deque = deque()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Semaphore({self.name}, {self.value})"


class CondVar:
    def __init__(self, name: str, monitor: "Monitor") -> None:
        self.name = name
        self.monitor = monitor
        self.waiters: deque = deque()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CondVar({self.name})"


class Monitor:
    def __init__(self, name: str) -> None:
        self.name = name
        self.frame = Frame()
        self.conds: dict[str, CondVar] = {}
        self.procs: dict[str, Any] = {}
        self.init: Any = None
        self.owner: "Process | None" = None
        # The monitor lock is an ordinary binary semaphore.
        self.mutex = Semaphore(f"{name}.mutex", 1)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Monitor({self.name})"


class Process:
    def __init__(self, pid: int, name: str, gen) -> None:
        self.pid = pid
        self.name = name
        self.gen = gen
        self.state = "ready"  # ready | blocked | done
        self.quantum_left = 0
        self.blocked_on: Any = None
        self.steps = 0
        self.result: Any = None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Process({self.pid}, {self.name}, {self.state})"


# -- events yielded by the interpreter -------------------------------------
@dataclass
class Step:
    node: Any = None
    detail: str = ""


@dataclass
class Block:
    obj: Any = None
    reason: str = ""


@dataclass
class Done:
    pass


@dataclass
class Spawn:
    name: str = ""
    func: Any = None
    args: list = field(default_factory=list)
