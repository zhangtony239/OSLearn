"""Recursive-descent parser for the .os pseudo-code language.

In lenient mode the parser never gives up on a statement it does not
understand: it records a warning and skips to the next ``;``.  That is what
lets textbook fragments such as ``produce an item in nextp;`` run.
"""

from __future__ import annotations

from . import ast_nodes as A
from .errors import ParseError
from .lexer import TYPE_KEYWORDS, Token

_ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=", "%=")


class Parser:
    def __init__(self, tokens: list[Token], filename: str = "<input>", lenient: bool = True) -> None:
        self.toks = tokens
        self.pos = 0
        self.filename = filename
        self.lenient = lenient
        self.warnings: list[str] = []

    # -- token helpers -----------------------------------------------------
    def peek(self, k: int = 0) -> Token:
        j = self.pos + k
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def at(self, kind: str, value=None) -> bool:
        t = self.peek()
        if t.kind != kind:
            return False
        return value is None or t.value == value

    def advance(self) -> Token:
        t = self.peek()
        if t.kind != "eof":
            self.pos += 1
        return t

    def match(self, kind: str, value=None) -> Token | None:
        if self.at(kind, value):
            return self.advance()
        return None

    def expect(self, kind: str, value=None) -> Token:
        if self.at(kind, value):
            return self.advance()
        t = self.peek()
        raise ParseError(
            f"expected {value or kind}, got {t.value!r}", t.line, t.col, self.filename
        )

    def warn(self, msg: str, tok: Token | None = None) -> None:
        tok = tok or self.peek()
        self.warnings.append(f"{self.filename}:{tok.line}:{tok.col}: {msg}")

    # -- recovery ----------------------------------------------------------
    def skip_to_semicolon(self) -> None:
        depth = 0
        while not self.at("eof"):
            t = self.peek()
            if t.kind == "op" and t.value in ("(", "[", "{"):
                depth += 1
            elif t.kind == "op" and t.value in (")", "]", "}"):
                if depth == 0:
                    return
                depth -= 1
            elif t.kind == "op" and t.value == ";" and depth == 0:
                self.advance()
                return
            self.advance()

    def skip_statement(self, msg: str) -> None:
        self.warn(msg)
        self.skip_to_semicolon()

    def skip_balanced_block(self) -> None:
        depth = 0
        while not self.at("eof"):
            t = self.peek()
            if t.kind == "op" and t.value == "{":
                depth += 1
            elif t.kind == "op" and t.value == "}":
                depth -= 1
                self.advance()
                if depth <= 0:
                    return
                continue
            self.advance()

    def skip_section(self) -> None:
        """Skip a ``share ...;`` style section header."""
        while not self.at("eof"):
            t = self.peek()
            if t.kind == "op" and t.value == ";":
                self.advance()
                return
            if t.kind == "op" and t.value in ("{", "}"):
                return
            if t.kind == "kw" and t.value in ("cond", "public", "private", "share"):
                return
            self.advance()

    def end_statement(self) -> None:
        if self.match("op", ";"):
            return
        if self.lenient:
            self.warn("missing ';'")
            self.skip_to_semicolon()
            return
        t = self.peek()
        raise ParseError(f"expected ';', got {t.value!r}", t.line, t.col, self.filename)

    # -- program -----------------------------------------------------------
    def parse_program(self) -> A.Program:
        items: list = []
        while not self.at("eof"):
            t = self.peek()
            if t.kind == "kw" and t.value == "monitor":
                items.append(self.parse_monitor())
            elif t.kind == "kw" and t.value == "semaphore":
                items.append(self.parse_semaphore_decl())
            elif t.kind == "kw" and t.value in TYPE_KEYWORDS:
                items.append(self.parse_decl_or_func())
            elif t.kind == "op" and t.value == ";":
                self.advance()
            else:
                self.skip_statement(f"unexpected top-level token {t.value!r}")
        return A.Program(items=items)

    def parse_decl_or_func(self):
        start = self.peek()
        type_name = self.advance().value
        if self.at("op", "("):
            # ``void (……) {……}`` placeholder from the textbook
            self.skip_balanced_block()
            return A.Empty(line=start.line)
        if not self.at("ident"):
            self.skip_statement(f"expected identifier after {type_name}")
            return A.Empty(line=start.line)
        name = self.advance().value
        if self.at("op", "("):
            params = self.parse_params()
            body = self.parse_block()
            return A.FuncDecl(name=name, params=params, body=body, ret_type=type_name, line=start.line)

        items: list = []
        while True:
            size = None
            init = None
            if self.match("op", "["):
                size = self.parse_expr()
                self.expect("op", "]")
            if self.match("op", "="):
                init = self.parse_expr()
            items.append((name, init, size))
            if not self.match("op", ","):
                break
            name = self.expect("ident").value
        self.end_statement()
        return A.VarDecl(type_name=type_name, items=items, line=start.line)

    def parse_params(self) -> list:
        self.expect("op", "(")
        params: list = []
        if not self.at("op", ")"):
            while True:
                if self.at("kw", "void") and self.peek(1).kind == "op" and self.peek(1).value == ")":
                    self.advance()
                    break
                if self.at("kw") and self.peek().value in TYPE_KEYWORDS:
                    self.advance()
                if self.at("ident"):
                    params.append(self.advance().value)
                else:
                    self.advance()
                if not self.match("op", ","):
                    break
        self.expect("op", ")")
        return params

    def parse_semaphore_decl(self) -> A.SemDecl:
        start = self.advance()
        items: list = []
        while True:
            name = self.expect("ident").value
            init = None
            if self.match("op", "="):
                init = self.parse_expr()
            items.append((name, init))
            if not self.match("op", ","):
                break
        self.end_statement()
        return A.SemDecl(items=items, line=start.line)

    def parse_monitor(self) -> A.MonitorDecl:
        start = self.advance()
        name = self.expect("ident").value
        self.expect("op", "{")
        vars_: list = []
        conds: list = []
        procs: list = []
        init = None
        while not self.at("op", "}") and not self.at("eof"):
            t = self.peek()
            if t.kind == "kw" and t.value == "share":
                self.advance()
                self.skip_section()
            elif t.kind == "kw" and t.value == "cond":
                self.advance()
                while self.at("ident"):
                    conds.append(self.advance().value)
                    if not self.match("op", ","):
                        break
                self.end_statement()
            elif t.kind == "kw" and t.value in ("public", "private"):
                self.advance()
                self.match("op", ":")
            elif t.kind == "kw" and t.value in TYPE_KEYWORDS:
                decl = self.parse_decl_or_func()
                if isinstance(decl, A.FuncDecl):
                    procs.append(decl)
                elif isinstance(decl, A.VarDecl):
                    vars_.append(decl)
            elif t.kind == "op" and t.value == "{":
                init = self.parse_block()
            elif t.kind == "op" and t.value == ";":
                self.advance()
            else:
                self.skip_statement(f"unexpected token in monitor body: {t.value!r}")
        self.expect("op", "}")
        return A.MonitorDecl(
            name=name, vars=vars_, conds=conds, procs=procs, init=init, line=start.line
        )

    # -- statements --------------------------------------------------------
    def parse_block(self) -> A.Block:
        start = self.expect("op", "{")
        stmts: list = []
        while not self.at("op", "}") and not self.at("eof"):
            stmts.append(self.parse_stmt())
        self.expect("op", "}")
        return A.Block(stmts=stmts, line=start.line)

    def parse_stmt(self):
        t = self.peek()
        if t.kind == "op" and t.value == "{":
            return self.parse_block()
        if t.kind == "op" and t.value == ";":
            self.advance()
            return A.Empty(line=t.line)
        if t.kind == "kw":
            v = t.value
            if v == "if":
                return self.parse_if()
            if v == "while":
                return self.parse_while()
            if v == "do":
                return self.parse_do()
            if v == "for":
                return self.parse_for()
            if v == "return":
                self.advance()
                value = None
                if not self.at("op", ";"):
                    value = self.parse_expr()
                self.end_statement()
                return A.Return(value=value, line=t.line)
            if v in ("break", "continue"):
                self.advance()
                self.end_statement()
                return A.Break(line=t.line) if v == "break" else A.Continue(line=t.line)
            if v in TYPE_KEYWORDS:
                return self.parse_decl_or_func()
            if v == "semaphore":
                return self.parse_semaphore_decl()
            if v == "monitor":
                return self.parse_monitor()
        if t.kind == "ident" and t.value.lower() in ("swait", "ssignal"):
            return self.parse_swait_ssignal()

        expr = self.parse_expr()
        if self.at("op", ";"):
            self.advance()
        elif self.lenient:
            self.warn("missing ';' after statement")
            self.skip_to_semicolon()
        else:
            self.expect("op", ";")
        return A.ExprStmt(expr=expr, line=t.line)

    def parse_if(self) -> A.If:
        start = self.advance()
        self.expect("op", "(")
        cond = self.parse_expr()
        self.expect("op", ")")
        then = self.parse_stmt()
        orelse = None
        if self.at("kw", "else"):
            self.advance()
            orelse = self.parse_stmt()
        return A.If(cond=cond, then=then, orelse=orelse, line=start.line)

    def parse_while(self) -> A.While:
        start = self.advance()
        self.expect("op", "(")
        cond = self.parse_expr()
        self.expect("op", ")")
        body = self.parse_stmt()
        return A.While(cond=cond, body=body, line=start.line)

    def parse_do(self) -> A.DoWhile:
        start = self.advance()
        body = self.parse_stmt()
        self.expect("kw", "while")
        self.expect("op", "(")
        cond = self.parse_expr()
        self.expect("op", ")")
        self.end_statement()
        return A.DoWhile(body=body, cond=cond, line=start.line)

    def parse_for(self) -> A.For:
        start = self.advance()
        self.expect("op", "(")
        init = None
        if self.at("op", ";"):
            self.advance()
        elif self.at("kw") and self.peek().value in TYPE_KEYWORDS:
            init = self.parse_decl_or_func()
        else:
            init = A.ExprStmt(expr=self.parse_expr(), line=start.line)
            self.match("op", ";")
        cond = None
        if not self.at("op", ";"):
            cond = self.parse_expr()
        self.expect("op", ";")
        update = None
        if not self.at("op", ")"):
            update = A.ExprStmt(expr=self.parse_expr(), line=start.line)
        self.expect("op", ")")
        body = self.parse_stmt()
        return A.For(init=init, cond=cond, update=update, body=body, line=start.line)

    def parse_swait_ssignal(self):
        start = self.advance()
        name = start.value.lower()
        self.expect("op", "(")
        if name == "swait":
            groups: list = []
            while not self.at("op", ")") and not self.at("eof"):
                sem = self.parse_expr()
                self.expect("op", ",")
                test = self.parse_expr()
                self.expect("op", ",")
                demand = self.parse_expr()
                groups.append((sem, test, demand))
                if not self.match("op", ";"):
                    break
            self.expect("op", ")")
            self.end_statement()
            return A.Swait(groups=groups, line=start.line)

        args: list = []
        while not self.at("op", ")") and not self.at("eof"):
            args.append(self.parse_expr())
            if not self.match("op", ","):
                break
        self.expect("op", ")")
        self.end_statement()
        return A.Ssignal(args=args, line=start.line)

    # -- expressions -------------------------------------------------------
    def parse_expr(self):
        return self.parse_assign()

    def parse_assign(self):
        left = self.parse_or()
        t = self.peek()
        if t.kind == "op" and t.value in _ASSIGN_OPS:
            self.advance()
            right = self.parse_assign()
            return A.Assign(target=left, op=t.value, value=right, line=t.line)
        return left

    def parse_or(self):
        left = self.parse_and()
        while self.at("op", "||"):
            op = self.advance()
            left = A.BinOp(op="||", left=left, right=self.parse_and(), line=op.line)
        return left

    def parse_and(self):
        left = self.parse_equality()
        while self.at("op", "&&"):
            op = self.advance()
            left = A.BinOp(op="&&", left=left, right=self.parse_equality(), line=op.line)
        return left

    def parse_equality(self):
        left = self.parse_relational()
        while self.at("op", "==") or self.at("op", "!="):
            op = self.advance()
            left = A.BinOp(op=op.value, left=left, right=self.parse_relational(), line=op.line)
        return left

    def parse_relational(self):
        left = self.parse_additive()
        while self.peek().kind == "op" and self.peek().value in ("<", "<=", ">", ">="):
            op = self.advance()
            left = A.BinOp(op=op.value, left=left, right=self.parse_additive(), line=op.line)
        return left

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.peek().kind == "op" and self.peek().value in ("+", "-"):
            op = self.advance()
            left = A.BinOp(op=op.value, left=left, right=self.parse_multiplicative(), line=op.line)
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while self.peek().kind == "op" and self.peek().value in ("*", "/", "%"):
            op = self.advance()
            left = A.BinOp(op=op.value, left=left, right=self.parse_unary(), line=op.line)
        return left

    def parse_unary(self):
        t = self.peek()
        if t.kind == "op" and t.value in ("!", "-", "+", "~"):
            self.advance()
            return A.UnOp(op=t.value, operand=self.parse_unary(), line=t.line)
        if t.kind == "op" and t.value in ("++", "--"):
            self.advance()
            return A.PreInc(op=t.value, target=self.parse_unary(), line=t.line)
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            t = self.peek()
            if t.kind == "op" and t.value == "(":
                self.advance()
                args: list = []
                while not self.at("op", ")") and not self.at("eof"):
                    args.append(self.parse_expr())
                    if not self.match("op", ","):
                        break
                self.expect("op", ")")
                expr = A.Call(callee=expr, args=args, line=t.line)
            elif t.kind == "op" and t.value == "[":
                self.advance()
                index = self.parse_expr()
                self.expect("op", "]")
                expr = A.Index(obj=expr, index=index, line=t.line)
            elif t.kind == "op" and t.value == ".":
                self.advance()
                name = self.expect("ident").value
                expr = A.Member(obj=expr, name=name, line=t.line)
            elif t.kind == "op" and t.value in ("++", "--"):
                self.advance()
                expr = A.PostInc(op=t.value, target=expr, line=t.line)
            else:
                break
        return expr

    def parse_primary(self):
        t = self.peek()
        if t.kind == "num":
            self.advance()
            return A.Num(value=t.value, line=t.line)
        if t.kind == "str":
            self.advance()
            return A.Str(value=t.value, line=t.line)
        if t.kind == "kw" and t.value in ("true", "false"):
            self.advance()
            return A.Bool(value=t.value == "true", line=t.line)
        if t.kind == "kw" and t.value == "null":
            self.advance()
            return A.Num(value=0, line=t.line)
        if t.kind == "ident":
            self.advance()
            return A.Var(name=t.value, line=t.line)
        if t.kind == "op" and t.value == "(":
            self.advance()
            expr = self.parse_expr()
            self.expect("op", ")")
            return expr
        raise ParseError(f"unexpected token {t.value!r}", t.line, t.col, self.filename)
