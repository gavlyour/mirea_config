from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, Optional

from .errors import ConfigLexError, SourcePos


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    pos: SourcePos


# По заданию "Числа:" указаны в научной нотации (экспонента обязательна)
_NUMBER_RE = re.compile(r"[+-]?\d+\.?\d*[eE][+-]?\d+")
_NAME_RE = re.compile(r"[_a-zA-Z]+")


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.line = 1
        self.col = 1

    def _pos(self) -> SourcePos:
        return SourcePos(self.line, self.col)

    def _peek(self, n: int = 0) -> str:
        j = self.i + n
        if j >= len(self.text):
            return ""
        return self.text[j]

    def _advance(self, n: int = 1) -> None:
        for _ in range(n):
            if self.i >= len(self.text):
                return
            ch = self.text[self.i]
            self.i += 1
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1

    def _match_regex(self, rx: re.Pattern) -> Optional[str]:
        m = rx.match(self.text, self.i)
        if not m:
            return None
        return m.group(0)

    def _skip_ws_and_comments(self) -> None:
        while True:
            ch = self._peek()

            # whitespace
            if ch and ch.isspace():
                self._advance(1)
                continue

            # однострочный комментарий: строка, начинающаяся с "
            if ch == '"':
                # до конца строки
                while self._peek() not in ("", "\n"):
                    self._advance(1)
                continue

            # многострочный комментарий /* ... */
            if ch == "/" and self._peek(1) == "*":
                start = self._pos()
                self._advance(2)
                while True:
                    if self._peek() == "" :
                        raise ConfigLexError("Unterminated multiline comment '/* ... */'", start)
                    if self._peek() == "*" and self._peek(1) == "/":
                        self._advance(2)
                        break
                    self._advance(1)
                continue

            break

    def tokens(self) -> Iterator[Token]:
        while True:
            self._skip_ws_and_comments()
            pos = self._pos()
            ch = self._peek()
            if ch == "":
                yield Token("EOF", "", pos)
                return

            # string: '...'
            if ch == "'":
                yield self._read_string()
                continue

            # multi-char operators
            if ch == ":" and self._peek(1) == "=":
                self._advance(2)
                yield Token("ASSIGN", ":=", pos)
                continue

            if ch == "$" and self._peek(1) == "[":
                self._advance(2)
                yield Token("CONST_OPEN", "$[", pos)
                continue

            # single-char punctuation
            if ch == "{":
                self._advance(1)
                yield Token("LBRACE", "{", pos)
                continue
            if ch == "}":
                self._advance(1)
                yield Token("RBRACE", "}", pos)
                continue
            if ch == "(":
                self._advance(1)
                yield Token("LPAREN", "(", pos)
                continue
            if ch == ")":
                self._advance(1)
                yield Token("RPAREN", ")", pos)
                continue
            if ch == ",":
                self._advance(1)
                yield Token("COMMA", ",", pos)
                continue
            if ch == "=":
                self._advance(1)
                yield Token("EQUAL", "=", pos)
                continue
            if ch == "]":
                self._advance(1)
                yield Token("RBRACK", "]", pos)
                continue

            # number
            num = self._match_regex(_NUMBER_RE)
            if num is not None:
                self._advance(len(num))
                yield Token("NUMBER", num, pos)
                continue

            # name
            name = self._match_regex(_NAME_RE)
            if name is not None:
                self._advance(len(name))
                yield Token("NAME", name, pos)
                continue

            raise ConfigLexError(f"Unexpected character: {ch!r}", pos)

    def _read_string(self) -> Token:
        pos = self._pos()
        assert self._peek() == "'"
        self._advance(1)
        out = []
        while True:
            ch = self._peek()
            if ch == "":
                raise ConfigLexError("Unterminated string literal", pos)
            if ch == "'":
                self._advance(1)
                return Token("STRING", "".join(out), pos)
            if ch == "\\":
                self._advance(1)
                esc = self._peek()
                if esc == "":
                    raise ConfigLexError("Unterminated escape sequence", self._pos())
                mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'"}
                out.append(mapping.get(esc, esc))
                self._advance(1)
                continue
            out.append(ch)
            self._advance(1)
