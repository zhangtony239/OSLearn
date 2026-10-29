"""Generator based interpreter.

Every statement is executed inside a generator.  The generator yields a
:class:`~vm.runtime.Step` after each statement (a scheduling point) and a
:class:`~vm.runtime.Block` when the process has to wait.  The scheduler drives
these generators, which makes cooperative concurrency trivial to express.
"""

from __future__ import annotations

from typing import Any

from . import ast_nodes as A
from .errors import VMRuntimeError
from .pretty import describe
from .runtime import Block, CondVar, Frame, Monitor, Process, Semaphore, Step


class ReturnSignal(Exception):
    def __init__(self, value: Any = 0) -> None:
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class ExitSignal(Exception):
    pass


class Interpreter:
    def __init__(self, config: dict, emit=None, trace=None) -> None:
        self.cfg = config
        self.globals = Frame()
        self.funcs: dict[str, A.FuncDecl] = {}
        self.monitors: dict[str, Monitor] = {}
        self.semaphores: dict[str, Semaphore] = {}
        self.processes: list[Process] = []
        self.current: Process | None = None
        self.sched = None
        self.warnings: list[str] = []

        self.emit = emit or (lambda s: print(s))
        self.trace = trace or (lambda s: print(s))
        self.auto_declare = bool(config["language"]["auto_declare"])
        self.lenient = bool(config["language"]["lenient"])

    # -- program entry -----------------------------------------------------
    def run(self, program: A.Program) -> None:
        for item in program.items:
            if isinstance(item, A.VarDecl):
                self.run_sync(self.exec_stmt(item, self.globals))
            elif isinstance(item, A.SemDecl):
                self.run_sync(self.exec_stmt(item, self.globals))
            elif isinstance(item, A.FuncDecl):
                self.funcs[item.name] = item
            elif isinstance(item, A.MonitorDecl):
                self.define_monitor(item)

        for mon in self.monitors.values():
            if mon.init is not None:
                self.run_sync(self.exec_stmt(mon.init, mon.frame))

        for func in list(self.funcs.values()):
            if func.ret_type == "void" and not func.params:
                self.sched.spawn(func.name, func, [])

        self.sched.run()

    def define_monitor(self, decl: A.MonitorDecl) -> None:
        mon = Monitor(decl.name)
        mon.frame.parent = self.globals
        for vd in decl.vars:
            self.run_sync(self.exec_stmt(vd, mon.frame))
        for cname in decl.conds:
            cond = CondVar(cname, mon)
            mon.conds[cname] = cond
            mon.frame.vars[cname] = cond
        for proc in decl.procs:
            mon.procs[proc.name] = proc
        mon.init = decl.init
        self.monitors[decl.name] = mon
        self.globals.vars[decl.name] = mon

    def run_sync(self, gen) -> Any:
        """Drive a generator to completion, rejecting blocking operations."""
        try:
            while True:
                ev = next(gen)
                if isinstance(ev, Block):
                    raise VMRuntimeError(
                        f"blocking operation ({ev.reason}) is not allowed here"
                    )
        except StopIteration as stop:
            return stop.value

    # -- statements --------------------------------------------------------
    def exec_stmt(self, node, frame: Frame):  # noqa: C901 - flat dispatch
        if isinstance(node, A.Block):
            for stmt in node.stmts:
                yield from self.exec_stmt(stmt, frame)
            return

        if isinstance(node, A.Empty):
            yield Step(node, ";")
            return

        if isinstance(node, A.VarDecl):
            yield Step(node, describe(node))
            for name, init, size in node.items:
                if size is not None:
                    n = self.eval(size, frame)
                    value = [0] * n if isinstance(n, int) and n > 0 else {}
                elif init is not None:
                    value = yield from self.eval_async(init, frame)
                else:
                    value = 0
                frame.vars[name] = value
            return

        if isinstance(node, A.SemDecl):
            for name, init in node.items:
                value = self.eval(init, frame) if init is not None else 0
                sem = Semaphore(name, int(value) if isinstance(value, (int, float)) else 0)
                frame.vars[name] = sem
                self.semaphores[name] = sem
            yield Step(node, describe(node))
            return

        if isinstance(node, A.If):
            cond = self.eval(node.cond, frame)
            yield Step(node, f"if ({describe(node.cond)}) -> {self.to_str(bool(cond))}")
            if cond:
                yield from self.exec_stmt(node.then, frame)
            elif node.orelse is not None:
                yield from self.exec_stmt(node.orelse, frame)
            return

        if isinstance(node, A.While):
            while True:
                cond = self.eval(node.cond, frame)
                yield Step(node, f"while ({describe(node.cond)}) -> {self.to_str(bool(cond))}")
                if not cond:
                    break
                try:
                    yield from self.exec_stmt(node.body, frame)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return

        if isinstance(node, A.DoWhile):
            while True:
                try:
                    yield from self.exec_stmt(node.body, frame)
                except BreakSignal:
                    break
                except ContinueSignal:
                    pass
                cond = self.eval(node.cond, frame)
                yield Step(node, f"do-while ({describe(node.cond)}) -> {self.to_str(bool(cond))}")
                if not cond:
                    break
            return

        if isinstance(node, A.For):
            if node.init is not None:
                yield from self.exec_stmt(node.init, frame)
            while True:
                if node.cond is not None:
                    cond = self.eval(node.cond, frame)
                    yield Step(node, f"for ({describe(node.cond)}) -> {self.to_str(bool(cond))}")
                    if not cond:
                        break
                else:
                    yield Step(node, "for")
                try:
                    yield from self.exec_stmt(node.body, frame)
                except BreakSignal:
                    break
                except ContinueSignal:
                    pass
                if node.update is not None:
                    yield from self.exec_stmt(node.update, frame)
            return

        if isinstance(node, A.Return):
            value = (yield from self.eval_async(node.value, frame)) if node.value is not None else 0
            yield Step(node, describe(node))
            raise ReturnSignal(value)

        if isinstance(node, A.Break):
            yield Step(node, "break")
            raise BreakSignal()

        if isinstance(node, A.Continue):
            yield Step(node, "continue")
            raise ContinueSignal()

        if isinstance(node, A.Swait):
            yield from self.do_swait(node, frame)
            return

        if isinstance(node, A.Ssignal):
            self.do_ssignal(node, frame)
            yield Step(node, describe(node))
            return

        if isinstance(node, A.ExprStmt):
            yield Step(node, describe(node))
            expr = node.expr
            if isinstance(expr, A.Call):
                yield from self.exec_call(expr, frame)
            elif isinstance(expr, A.Assign) and isinstance(expr.value, A.Call):
                value = yield from self.exec_call(expr.value, frame)
                self.assign_to(expr.target, value, frame)
            else:
                self.eval(expr, frame)
            return

        raise VMRuntimeError(f"cannot execute {type(node).__name__}")

    # -- semaphores --------------------------------------------------------
    def do_P(self, sem: Semaphore):
        while sem.value <= 0:
            yield Block(sem, f"P({sem.name})")
        sem.value -= 1

    def do_V(self, sem: Semaphore, n: int = 1) -> None:
        for _ in range(max(1, int(n))):
            sem.value += 1
            if sem.waiters:
                self.sched.wake(sem.waiters.popleft())

    def do_swait(self, node: A.Swait, frame: Frame):
        groups = [
            (self.eval(s, frame), self.eval(t, frame), self.eval(d, frame))
            for s, t, d in node.groups
        ]
        while True:
            bad = None
            for sem, test, _demand in groups:
                if not isinstance(sem, Semaphore):
                    raise VMRuntimeError("Swait expects a semaphore as its first argument")
                if sem.value < test:
                    bad = sem
                    break
            if bad is None:
                break
            yield Block(bad, f"Swait({bad.name})")
        for sem, _test, demand in groups:
            sem.value -= demand
        yield Step(node, describe(node))

    def do_ssignal(self, node: A.Ssignal, frame: Frame) -> None:
        values = [self.eval(a, frame) for a in node.args]
        i = 0
        while i + 1 < len(values):
            sem, demand = values[i], values[i + 1]
            if isinstance(sem, Semaphore):
                self.do_V(sem, demand)
            i += 2

    # -- monitors ----------------------------------------------------------
    def enter_monitor(self, mon: Monitor):
        yield from self.do_P(mon.mutex)
        mon.owner = self.current

    def exit_monitor(self, mon: Monitor) -> None:
        mon.owner = None
        self.do_V(mon.mutex)

    def cond_wait(self, cond: CondVar):
        mon = cond.monitor
        mon.owner = None
        self.do_V(mon.mutex)
        yield Block(cond, f"{cond.name}.wait")
        yield from self.do_P(mon.mutex)
        mon.owner = self.current

    def cond_signal(self, cond: CondVar) -> None:
        if cond.waiters:
            self.sched.wake(cond.waiters.popleft())

    # -- calls -------------------------------------------------------------
    def exec_call(self, node: A.Call, frame: Frame):
        callee = node.callee
        args = [self.eval(a, frame) for a in node.args]

        if isinstance(callee, A.Member):
            obj = self.eval(callee.obj, frame)
            if isinstance(obj, CondVar):
                op = callee.name.lower()
                if op in ("wait", "p"):
                    yield from self.cond_wait(obj)
                    return 0
                if op in ("signal", "v", "notify"):
                    self.cond_signal(obj)
                    return 0
                raise VMRuntimeError(f"unknown condition operation {callee.name!r}")
            if isinstance(obj, Monitor):
                proc = obj.procs.get(callee.name)
                if proc is None:
                    raise VMRuntimeError(
                        f"monitor {obj.name!r} has no procedure {callee.name!r}"
                    )
                yield from self.enter_monitor(obj)
                try:
                    return (yield from self.call_func(proc, args, parent=obj.frame))
                finally:
                    self.exit_monitor(obj)
            raise VMRuntimeError(f"cannot call member {callee.name!r}")

        if not isinstance(callee, A.Var):
            raise VMRuntimeError("unsupported call target")

        name = callee.name
        low = name.lower()

        if low in ("p", "wait"):
            sem = args[0] if args else None
            if not isinstance(sem, Semaphore):
                raise VMRuntimeError("P()/wait() expects a semaphore")
            yield from self.do_P(sem)
            return 0

        if low in ("v", "signal"):
            sem = args[0] if args else None
            if not isinstance(sem, Semaphore):
                raise VMRuntimeError("V()/signal() expects a semaphore")
            self.do_V(sem, args[1] if len(args) > 1 else 1)
            return 0

        if low in ("print", "printf", "println"):
            self.bi_print(args)
            return 0

        if low in ("start", "fork", "spawn"):
            if node.args and isinstance(node.args[0], A.Var):
                fname = node.args[0].name
                func = self.funcs.get(fname)
                if func is None:
                    raise VMRuntimeError(f"cannot start unknown function {fname!r}")
                rest = [self.eval(a, frame) for a in node.args[1:]]
                self.sched.spawn(fname, func, rest)
                return 0
            raise VMRuntimeError("start() expects a function name")

        if low in ("exit", "halt"):
            raise ExitSignal()

        if name in self.funcs:
            return (yield from self.call_func(self.funcs[name], args))

        if name in self.monitors:
            raise VMRuntimeError(
                f"{name!r} is a monitor; call one of its procedures instead"
            )

        if self.lenient:
            self.warnings.append(f"unknown function {name!r} ignored")
            return 0
        raise VMRuntimeError(f"unknown function {name!r}")

    def call_func(self, func: A.FuncDecl, args: list, parent: Frame | None = None):
        frame = Frame(parent=parent or self.globals)
        for i, pname in enumerate(func.params):
            frame.vars[pname] = args[i] if i < len(args) else 0
        try:
            yield from self.exec_stmt(func.body, frame)
        except ReturnSignal as ret:
            return ret.value
        return 0

    # -- expressions -------------------------------------------------------
    def eval_async(self, node, frame: Frame):
        """Evaluate an expression, allowing a top-level call to block."""
        if isinstance(node, A.Call):
            return (yield from self.exec_call(node, frame))
        return self.eval(node, frame)

    def eval(self, node, frame: Frame):  # noqa: C901 - flat dispatch
        if node is None:
            return 0
        if isinstance(node, A.Num):
            return node.value
        if isinstance(node, A.Str):
            return node.value
        if isinstance(node, A.Bool):
            return node.value
        if isinstance(node, A.Var):
            return self.get_var(node.name, frame)
        if isinstance(node, A.Index):
            obj = self.eval(node.obj, frame)
            idx = self.eval(node.index, frame)
            if isinstance(obj, list):
                if isinstance(idx, int) and 0 <= idx < len(obj):
                    return obj[idx]
                return 0
            if isinstance(obj, dict):
                return obj.get(idx, 0)
            return 0
        if isinstance(node, A.Member):
            obj = self.eval(node.obj, frame)
            return getattr(obj, node.name, 0)
        if isinstance(node, A.BinOp):
            return self.eval_binop(node, frame)
        if isinstance(node, A.UnOp):
            value = self.eval(node.operand, frame)
            if node.op == "!":
                return not self.truthy(value)
            if node.op == "-":
                return -self.num(value)
            if node.op == "+":
                return self.num(value)
            if node.op == "~":
                return ~int(self.num(value))
        if isinstance(node, A.Assign):
            return self.eval_assign(node, frame)
        if isinstance(node, A.PostInc):
            old = self.eval(node.target, frame)
            self.assign_to(node.target, self.num(old) + (1 if node.op == "++" else -1), frame)
            return old
        if isinstance(node, A.PreInc):
            new = self.num(self.eval(node.target, frame)) + (1 if node.op == "++" else -1)
            self.assign_to(node.target, new, frame)
            return new
        if isinstance(node, A.Call):
            return self.run_sync(self.exec_call(node, frame))
        raise VMRuntimeError(f"cannot evaluate {type(node).__name__}")

    def eval_binop(self, node: A.BinOp, frame: Frame):
        op = node.op
        if op == "&&":
            if not self.truthy(self.eval(node.left, frame)):
                return False
            return self.truthy(self.eval(node.right, frame))
        if op == "||":
            if self.truthy(self.eval(node.left, frame)):
                return True
            return self.truthy(self.eval(node.right, frame))

        left = self.eval(node.left, frame)
        right = self.eval(node.right, frame)
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self.to_str(left) + self.to_str(right)
            return self.num(left) + self.num(right)
        if op == "-":
            return self.num(left) - self.num(right)
        if op == "*":
            return self.num(left) * self.num(right)
        if op == "/":
            if self.num(right) == 0:
                raise VMRuntimeError("division by zero")
            return self.num(left) / self.num(right)
        if op == "%":
            if self.num(right) == 0:
                raise VMRuntimeError("modulo by zero")
            return self.num(left) % self.num(right)
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return self.num(left) < self.num(right)
        if op == "<=":
            return self.num(left) <= self.num(right)
        if op == ">":
            return self.num(left) > self.num(right)
        if op == ">=":
            return self.num(left) >= self.num(right)
        raise VMRuntimeError(f"unsupported operator {op!r}")

    def eval_assign(self, node: A.Assign, frame: Frame):
        if node.op == "=":
            value = self.eval(node.value, frame)
        else:
            current = self.eval(node.target, frame)
            value = self.eval_binop(
                A.BinOp(op=node.op[0], left=A.Num(value=current), right=node.value), frame
            )
        self.assign_to(node.target, value, frame)
        return value

    # -- variables ---------------------------------------------------------
    def get_var(self, name: str, frame: Frame):
        f: Frame | None = frame
        while f is not None:
            if name in f.vars:
                return f.vars[name]
            f = f.parent
        if self.auto_declare:
            self.globals.vars[name] = 0
            return 0
        raise VMRuntimeError(f"undefined variable {name!r}")

    def set_var(self, name: str, value, frame: Frame) -> None:
        f: Frame | None = frame
        while f is not None:
            if name in f.vars:
                f.vars[name] = value
                return
            f = f.parent
        self.globals.vars[name] = value

    def assign_to(self, target, value, frame: Frame) -> None:
        if isinstance(target, A.Var):
            self.set_var(target.name, value, frame)
            return
        if isinstance(target, A.Index):
            container = self.eval(target.obj, frame)
            idx = self.eval(target.index, frame)
            if not isinstance(container, (list, dict)):
                container = {}
                self.assign_to(target.obj, container, frame)
            if isinstance(container, list):
                if not isinstance(idx, int):
                    raise VMRuntimeError("array index must be an integer")
                while len(container) <= idx:
                    container.append(0)
                container[idx] = value
            else:
                container[idx] = value
            return
        raise VMRuntimeError("invalid assignment target")

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def num(value) -> float | int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    @staticmethod
    def truthy(value) -> bool:
        if isinstance(value, str):
            return value != ""
        return bool(value)

    @staticmethod
    def to_str(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def bi_print(self, args: list) -> None:
        if args and isinstance(args[0], str) and "%" in args[0]:
            self.emit(self.format_printf(args[0], args[1:]))
            return
        self.emit(" ".join(self.to_str(a) for a in args))

    def format_printf(self, fmt: str, args: list) -> str:
        out: list[str] = []
        i = 0
        ai = 0
        while i < len(fmt):
            ch = fmt[i]
            if ch == "%" and i + 1 < len(fmt):
                spec = fmt[i + 1]
                if spec == "%":
                    out.append("%")
                    i += 2
                    continue
                if spec in "dixXcsf":
                    value = args[ai] if ai < len(args) else 0
                    ai += 1
                    if spec in "dixX":
                        out.append(str(int(self.num(value))))
                    elif spec == "c":
                        out.append(chr(int(self.num(value))))
                    elif spec == "f":
                        out.append(f"{float(self.num(value)):.6f}")
                    else:
                        out.append(self.to_str(value))
                    i += 2
                    continue
            out.append(ch)
            i += 1
        return "".join(out)
