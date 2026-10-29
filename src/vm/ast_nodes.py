"""AST node definitions for the .os language."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    line: int = 0


# -- top level -------------------------------------------------------------
@dataclass
class Program(Node):
    items: list = field(default_factory=list)


@dataclass
class VarDecl(Node):
    type_name: str = "int"
    # list of (name, init_expr | None, size_expr | None)
    items: list = field(default_factory=list)


@dataclass
class SemDecl(Node):
    # list of (name, init_expr | None)
    items: list = field(default_factory=list)


@dataclass
class FuncDecl(Node):
    name: str = ""
    params: list = field(default_factory=list)
    body: Any = None
    ret_type: str = "void"


@dataclass
class MonitorDecl(Node):
    name: str = ""
    vars: list = field(default_factory=list)
    conds: list = field(default_factory=list)
    procs: list = field(default_factory=list)
    init: Any = None


# -- statements ------------------------------------------------------------
@dataclass
class Block(Node):
    stmts: list = field(default_factory=list)


@dataclass
class Empty(Node):
    pass


@dataclass
class If(Node):
    cond: Any = None
    then: Any = None
    orelse: Any = None


@dataclass
class While(Node):
    cond: Any = None
    body: Any = None


@dataclass
class DoWhile(Node):
    body: Any = None
    cond: Any = None


@dataclass
class For(Node):
    init: Any = None
    cond: Any = None
    update: Any = None
    body: Any = None


@dataclass
class Return(Node):
    value: Any = None


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class ExprStmt(Node):
    expr: Any = None


@dataclass
class Swait(Node):
    # list of (sem_expr, test_expr, demand_expr)
    groups: list = field(default_factory=list)


@dataclass
class Ssignal(Node):
    # flat list: sem, demand, sem, demand, ...
    args: list = field(default_factory=list)


# -- expressions -----------------------------------------------------------
@dataclass
class Num(Node):
    value: Any = 0


@dataclass
class Str(Node):
    value: str = ""


@dataclass
class Bool(Node):
    value: bool = False


@dataclass
class Var(Node):
    name: str = ""


@dataclass
class Index(Node):
    obj: Any = None
    index: Any = None


@dataclass
class Member(Node):
    obj: Any = None
    name: str = ""


@dataclass
class Call(Node):
    callee: Any = None
    args: list = field(default_factory=list)


@dataclass
class BinOp(Node):
    op: str = ""
    left: Any = None
    right: Any = None


@dataclass
class UnOp(Node):
    op: str = ""
    operand: Any = None


@dataclass
class Assign(Node):
    target: Any = None
    op: str = "="
    value: Any = None


@dataclass
class PostInc(Node):
    op: str = "++"
    target: Any = None


@dataclass
class PreInc(Node):
    op: str = "++"
    target: Any = None
