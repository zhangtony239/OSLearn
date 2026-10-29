"""Tokenizer for the .os pseudo-code language.

The language is deliberately forgiving: textbook snippets contain full-width
punctuation, Chinese comments, ellipses and natural-language statements.  The
lexer normalises full-width characters to ASCII and (in lenient mode) skips
characters it does not understand instead of failing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import LexError

TYPE_KEYWORDS = frozenset(
    {
        "void",
        "int",
        "char",
        "bool",
        "float",
        "double",
        "long",
        "short",
        "unsigned",
        "signed",
        "const",
        "static",
        "struct",
        "typedef",
        "enum",
        "union",
    }
)

KEYWORDS = TYPE_KEYWORDS | frozenset(
    {
        "if",
        "else",
        "while",
        "do",
        "for",
        "return",
        "break",
        "continue",
        "semaphore",
        "monitor",
        "share",
        "cond",
        "public",
        "private",
        "true",
        "false",
        "null",
        "switch",
        "case",
        "default",
        "goto",
        "sizeof",
        "extern",
        "register",
        "volatile",
    }
)

# Full-width / CJK punctuation that shows up in textbook pseudo-code.
_FW = {
    "；": ";",
    "，": ",",
    "（": "(",
    "）": ")",
    "：": ":",
    "｛": "{",
    "｝": "}",
    "＝": "=",
    "＋": "+",
    "－": "-",
    "＊": "*",
    "／": "/",
    "＜": "<",
    "＞": ">",
    "！": "!",
    "［": "[",
    "］": "]",
    "　": " ",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "％": "%",
    "＆": "&",
    "｜": "|",
    "～": "~",
    "＃": "#",
    "＠": "@",
    "…": " ",
    "⋯": " ",
    "·": " ",
}

_OPS = (
    "<<=",
    ">>=",
    "==",
    "!=",
    "<=",
    ">=",
    "&&",
    "||",
    "++",
    "--",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "->",
    "<<",
    ">>",
    "+",
    "-",
    "*",
    "/",
    "%",
    "=",
    "<",
    ">",
    "!",
    ";",
    ",",
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
    ":",
    "&",
    "|",
    "^",
    "~",
    "?",
    ".",
)


@dataclass
class Token:
    kind: str
    value: Any
    line: int
    col: int
    text: str = ""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"


def normalize(src: str) -> str:
    """Map full-width punctuation to ASCII, keeping line/column layout."""
    return "".join(_FW.get(ch, ch) for ch in src)


class Lexer:
    def __init__(self, src: str, case_insensitive: bool = True, lenient: bool = True) -> None:
        self.src = normalize(src)
        self.n = len(self.src)
        self.i = 0
        self.line = 1
        self.col = 1
        self.case_insensitive = case_insensitive
        self.lenient = lenient
        self.warnings: list[str] = []
        self.tokens: list[Token] = []

    # -- low level helpers -------------------------------------------------
    def _adv(self, k: int = 1) -> None:
        for _ in range(k):
            if self.i >= self.n:
                return
            if self.src[self.i] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.i += 1

    def _peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.src[j] if j < self.n else ""

    # -- public API --------------------------------------------------------
    def tokenize(self) -> list[Token]:
        while self.i < self.n:
            ch = self.src[self.i]
            if ch in " \t\r\n\f\v":
                self._adv()
                continue
            if ch == "#":  # preprocessor line, ignore
                while self.i < self.n and self.src[self.i] != "\n":
                    self._adv()
                continue
            if ch == "/" and self._peek(1) == "/":
                while self.i < self.n and self.src[self.i] != "\n":
                    self._adv()
                continue
            if ch == "/" and self._peek(1) == "*":
                self._adv(2)
                while self.i < self.n and not (
                    self.src[self.i] == "*" and self._peek(1) == "/"
                ):
                    self._adv()
                self._adv(2)
                continue
            if ch in "\"'":
                self._string(ch)
                continue
            if ch.isdigit():
                self._number()
                continue
            if ch.isalpha() or ch == "_":
                self._ident()
                continue
            if self._op():
                continue
            if self.lenient:
                self.warnings.append(
                    f"{self.line}:{self.col}: skipped unsupported character {ch!r}"
                )
                self._adv()
                continue
            raise LexError(f"unexpected character {ch!r}", self.line, self.col)
        self.tokens.append(Token("eof", None, self.line, self.col, ""))
        return self.tokens

    # -- scanners ----------------------------------------------------------
    def _string(self, quote: str) -> None:
        line, col = self.line, self.col
        self._adv()
        buf: list[str] = []
        while self.i < self.n and self.src[self.i] != quote:
            ch = self.src[self.i]
            if ch == "\\":
                self._adv()
                esc = self._peek()
                buf.append(
                    {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}.get(
                        esc, esc
                    )
                )
                self._adv()
                continue
            if ch == "\n":
                break
            buf.append(ch)
            self._adv()
        if self.i >= self.n or self.src[self.i] != quote:
            raise LexError("unterminated string literal", line, col)
        self._adv()
        text = "".join(buf)
        if quote == "'":
            self.tokens.append(Token("num", ord(text[0]) if text else 0, line, col, text))
        else:
            self.tokens.append(Token("str", text, line, col, text))

    def _number(self) -> None:
        line, col = self.line, self.col
        start = self.i
        if self.src[self.i] == "0" and self._peek(1) and self._peek(1) in "xX":
            self._adv(2)
            while self.i < self.n and (
                self.src[self.i].isdigit() or self.src[self.i].lower() in "abcdef"
            ):
                self._adv()
            text = self.src[start : self.i]
            try:
                value: Any = int(text, 16)
            except ValueError as exc:  # pragma: no cover - defensive
                raise LexError(f"bad hex literal {text!r}", line, col) from exc
            self.tokens.append(Token("num", value, line, col, text))
            return

        is_float = False
        while self.i < self.n and self.src[self.i].isdigit():
            self._adv()
        if self.i < self.n and self.src[self.i] == "." and self._peek(1).isdigit():
            is_float = True
            self._adv()
            while self.i < self.n and self.src[self.i].isdigit():
                self._adv()
        if self.i < self.n and self.src[self.i] in "eE":
            j = self.i + 1
            if j < self.n and self.src[j] in "+-":
                j += 1
            if j < self.n and self.src[j].isdigit():
                is_float = True
                self._adv(j - self.i)
                while self.i < self.n and self.src[self.i].isdigit():
                    self._adv()
        text = self.src[start : self.i]
        value = float(text) if is_float else int(text)
        self.tokens.append(Token("num", value, line, col, text))

    def _ident(self) -> None:
        line, col = self.line, self.col
        start = self.i
        while self.i < self.n and (self.src[self.i].isalnum() or self.src[self.i] == "_"):
            self._adv()
        text = self.src[start : self.i]
        key = text.lower() if self.case_insensitive else text
        if key in KEYWORDS:
            self.tokens.append(Token("kw", key, line, col, text))
        else:
            self.tokens.append(Token("ident", text, line, col, text))

    def _op(self) -> bool:
        for op in _OPS:
            if self.src.startswith(op, self.i):
                line, col = self.line, self.col
                self._adv(len(op))
                self.tokens.append(Token("op", op, line, col, op))
                return True
        return False
