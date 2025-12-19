from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePos:
    line: int
    col: int

    def __str__(self) -> str:
        return f"{self.line}:{self.col}"


class ConfigError(Exception):
    """Base error for the translator."""


class ConfigLexError(ConfigError):
    def __init__(self, message: str, pos: SourcePos):
        super().__init__(f"LexError at {pos}: {message}")
        self.pos = pos


class ConfigParseError(ConfigError):
    def __init__(self, message: str, pos: SourcePos):
        super().__init__(f"ParseError at {pos}: {message}")
        self.pos = pos


class ConfigEvalError(ConfigError):
    def __init__(self, message: str, pos: SourcePos | None = None):
        prefix = f"EvalError at {pos}: " if pos else "EvalError: "
        super().__init__(prefix + message)
        self.pos = pos
