from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Sequence

from .errors import ConfigParseError, SourcePos
from .lexer import Lexer, Token


@dataclass(frozen=True)
class ConstRef:
    name: str
    pos: SourcePos


def _normalize_number(s: str, pos: SourcePos) -> int | float:
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ConfigParseError(f"Invalid number literal: {s!r}", pos)
    if d == d.to_integral_value():
        return int(d)
    return float(d)


class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        self.i = 0

    def _cur(self) -> Token:
        return self.tokens[self.i]

    def _peek(self, n: int = 1) -> Token:
        j = self.i + n
        if j >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[j]

    def _eat(self, ttype: str) -> Token:
        tok = self._cur()
        if tok.type != ttype:
            raise ConfigParseError(f"Expected {ttype}, got {tok.type}", tok.pos)
        self.i += 1
        return tok

    def _try_eat(self, ttype: str) -> bool:
        if self._cur().type == ttype:
            self.i += 1
            return True
        return False

    def parse(self) -> tuple[dict[str, Any], Any]:
        # program := { const_decl } value EOF
        consts: dict[str, Any] = {}
        while self._cur().type == "NAME" and self._peek().type == "ASSIGN":
            name_tok = self._eat("NAME")
            self._eat("ASSIGN")
            if name_tok.value in consts:
                raise ConfigParseError(f"Duplicate constant declaration: {name_tok.value}", name_tok.pos)
            consts[name_tok.value] = self._value()
        root = self._value()
        self._eat("EOF")
        return consts, root

    def _value(self) -> Any:
        tok = self._cur()

        if tok.type == "NUMBER":
            self.i += 1
            return _normalize_number(tok.value, tok.pos)

        if tok.type == "STRING":
            self.i += 1
            return tok.value

        if tok.type == "LPAREN":
            return self._array()

        if tok.type == "LBRACE":
            return self._dict()

        if tok.type == "CONST_OPEN":
            return self._const_ref()

        raise ConfigParseError(f"Unexpected token in value: {tok.type}", tok.pos)

    def _const_ref(self) -> ConstRef:
        open_tok = self._eat("CONST_OPEN")
        name_tok = self._eat("NAME")
        self._eat("RBRACK")
        return ConstRef(name=name_tok.value, pos=open_tok.pos)

    def _array(self) -> List[Any]:
        self._eat("LPAREN")
        items: List[Any] = []

        if self._cur().type == "RPAREN":
            self._eat("RPAREN")
            return items

        items.append(self._value())
        while self._try_eat("COMMA"):
            items.append(self._value())

        self._eat("RPAREN")
        return items

    def _dict(self) -> Dict[str, Any]:
        self._eat("LBRACE")
        out: Dict[str, Any] = {}

        # entries: { NAME '=' value [','?] }*
        while self._cur().type == "NAME":
            key_tok = self._eat("NAME")
            self._eat("EQUAL")
            out[key_tok.value] = self._value()
            # допускаем необязательные запятые между парами, даже если в спецификации они не показаны
            self._try_eat("COMMA")

        self._eat("RBRACE")
        return out


def parse_text(text: str) -> tuple[dict[str, Any], Any]:
    lx = Lexer(text)
    toks = list(lx.tokens())
    return Parser(toks).parse()