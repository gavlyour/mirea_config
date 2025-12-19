from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ConfigEvalError
from .parser import ConstRef


@dataclass
class Evaluator:
    const_defs: dict[str, Any]

    def __post_init__(self) -> None:
        self._resolved: dict[str, Any] = {}
        self._resolving: list[str] = []  # stack for cycles

    def eval_root(self, root: Any) -> Any:
        return self._eval_node(root)

    def _eval_node(self, node: Any) -> Any:
        if isinstance(node, ConstRef):
            return self._resolve_const(node.name, node.pos)
        if isinstance(node, list):
            return [self._eval_node(x) for x in node]
        if isinstance(node, dict):
            return {k: self._eval_node(v) for k, v in node.items()}
        return node

    def _resolve_const(self, name: str, pos) -> Any:
        if name in self._resolved:
            return self._resolved[name]

        if name in self._resolving:
            cycle = " -> ".join(self._resolving + [name])
            raise ConfigEvalError(f"Cyclic constant reference: {cycle}", pos)

        if name not in self.const_defs:
            raise ConfigEvalError(f"Undefined constant: {name}", pos)

        self._resolving.append(name)
        try:
            val = self._eval_node(self.const_defs[name])
            self._resolved[name] = val
            return val
        finally:
            self._resolving.pop()
