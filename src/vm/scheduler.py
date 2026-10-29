"""Cooperative scheduler.

Two policies are supported:

``round_robin``
    Each process runs at most ``quantum`` statements before it is moved to the
    back of the ready queue.  Fully deterministic.

``random``
    A ready process is chosen at random for every step.  ``seed >= 0`` makes
    the interleaving reproducible, ``seed == -1`` picks a fresh seed per run.
"""

from __future__ import annotations

import random

from .pretty import describe
from .runtime import Block, Process, Step


class Scheduler:
    def __init__(
        self,
        interp,
        policy: str = "round_robin",
        quantum: int = 5,
        seed: int = -1,
        max_steps: int = 10000,
        trace_enabled: bool = True,
    ) -> None:
        self.interp = interp
        self.policy = policy
        self.quantum = max(1, int(quantum))
        self.max_steps = max(1, int(max_steps))
        self.trace_enabled = trace_enabled
        self.rng = random.Random(seed if seed is not None and seed >= 0 else None)
        self.ready: list[Process] = []
        self.processes: list[Process] = []
        self.steps = 0
        self.deadlock = False
        self.truncated = False

    # -- process management ------------------------------------------------
    def spawn(self, name: str, func, args: list) -> Process:
        proc = Process(len(self.processes), name, self.interp.call_func(func, args))
        proc.quantum_left = self.quantum
        self.processes.append(proc)
        self.ready.append(proc)
        self.trace_event(proc, "spawn")
        return proc

    def wake(self, proc: Process) -> None:
        if proc.state != "blocked":
            return
        proc.state = "ready"
        proc.blocked_on = None
        proc.quantum_left = self.quantum
        self.ready.append(proc)
        self.trace_event(proc, "WAKE")

    # -- main loop ---------------------------------------------------------
    def run(self) -> None:
        from .interpreter import ExitSignal, ReturnSignal

        while self.ready and self.steps < self.max_steps:
            proc = self.pick()
            self.interp.current = proc
            try:
                event = next(proc.gen)
            except StopIteration:
                proc.state = "done"
                self.trace_event(proc, "exit")
                continue
            except (ReturnSignal, ExitSignal):
                proc.state = "done"
                self.trace_event(proc, "exit")
                continue

            self.steps += 1
            proc.steps += 1

            if isinstance(event, Block):
                proc.state = "blocked"
                proc.blocked_on = event.obj
                event.obj.waiters.append(proc)
                self.trace_event(proc, f"BLOCK  {event.reason}")
                continue

            if isinstance(event, Step):
                self.trace_event(proc, event.detail or describe(event.node))

            self.reschedule(proc)

        if self.steps >= self.max_steps and self.ready:
            self.truncated = True
        if not self.ready and any(p.state == "blocked" for p in self.processes):
            self.deadlock = True

    def pick(self) -> Process:
        if self.policy == "random":
            index = self.rng.randrange(len(self.ready))
            return self.ready.pop(index)
        return self.ready.pop(0)

    def reschedule(self, proc: Process) -> None:
        if self.policy == "random":
            self.ready.append(proc)
            return
        proc.quantum_left -= 1
        if proc.quantum_left > 0:
            self.ready.insert(0, proc)
        else:
            proc.quantum_left = self.quantum
            self.ready.append(proc)

    # -- tracing -----------------------------------------------------------
    def trace_event(self, proc: Process, text: str) -> None:
        if not self.trace_enabled:
            return
        self.interp.trace(f"[{self.steps:04d}] {proc.name:<12} | {text}")
