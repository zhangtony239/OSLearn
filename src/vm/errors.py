"""Error types for the .os VM."""

from __future__ import annotations


class VMError(Exception):
    """Base class for every error raised by the VM."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        col: int | None = None,
        filename: str | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.col = col
        self.filename = filename
        super().__init__(self.render())

    def render(self) -> str:
        loc = self.filename or ""
        if self.line is not None:
            loc += f":{self.line}"
            if self.col is not None:
                loc += f":{self.col}"
        return f"{loc}: {self.message}" if loc else self.message


class LexError(VMError):
    """Raised when the tokenizer cannot make sense of the input."""


class ParseError(VMError):
    """Raised when the parser hits an unexpected token."""


class VMRuntimeError(VMError):
    """Raised when execution fails (undefined function, division by zero, ...)."""


class ConfigError(VMError):
    """Raised when vm-config.yaml is malformed."""
