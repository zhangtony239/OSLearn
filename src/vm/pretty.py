"""Turn AST nodes back into short, human readable snippets for tracing."""

from __future__ import annotations

from . import ast_nodes as A


def describe(node) -> str:  # noqa: C901 - a flat dispatch table is clearer here
    if node is None:
        return ""
    if isinstance(node, A.Num):
        return str(node.value)
    if isinstance(node, A.Str):
        escaped = node.value.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")
        return '"%s"' % escaped
    if isinstance(node, A.Bool):
        return "true" if node.value else "false"
    if isinstance(node, A.Var):
        return node.name
    if isinstance(node, A.Index):
        return f"{describe(node.obj)}[{describe(node.index)}]"
    if isinstance(node, A.Member):
        return f"{describe(node.obj)}.{node.name}"
    if isinstance(node, A.Call):
        return f"{describe(node.callee)}({', '.join(describe(a) for a in node.args)})"
    if isinstance(node, A.BinOp):
        return f"({describe(node.left)} {node.op} {describe(node.right)})"
    if isinstance(node, A.UnOp):
        return f"{node.op}{describe(node.operand)}"
    if isinstance(node, A.Assign):
        return f"{describe(node.target)} {node.op} {describe(node.value)}"
    if isinstance(node, A.PostInc):
        return f"{describe(node.target)}{node.op}"
    if isinstance(node, A.PreInc):
        return f"{node.op}{describe(node.target)}"
    if isinstance(node, A.ExprStmt):
        return describe(node.expr)
    if isinstance(node, A.VarDecl):
        return f"{node.type_name} " + ", ".join(n for n, _, _ in node.items)
    if isinstance(node, A.SemDecl):
        return "semaphore " + ", ".join(n for n, _ in node.items)
    if isinstance(node, A.If):
        return f"if ({describe(node.cond)})"
    if isinstance(node, A.While):
        return f"while ({describe(node.cond)})"
    if isinstance(node, A.DoWhile):
        return "do-while"
    if isinstance(node, A.For):
        return "for"
    if isinstance(node, A.Return):
        return "return" + (f" {describe(node.value)}" if node.value is not None else "")
    if isinstance(node, A.Break):
        return "break"
    if isinstance(node, A.Continue):
        return "continue"
    if isinstance(node, A.Empty):
        return ";"
    if isinstance(node, A.Swait):
        return "Swait(...)"
    if isinstance(node, A.Ssignal):
        return "Ssignal(...)"
    if isinstance(node, A.Block):
        return "{...}"
    return type(node).__name__
