from __future__ import annotations

import argparse
import json
import sys

from .errors import ConfigError
from .evaluator import Evaluator
from .parser import parse_text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="uconfig",
        description="Translator from учебный конфигурационный язык to JSON."
    )
    p.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output JSON file."
    )
    args = p.parse_args(argv)

    src = sys.stdin.read()

    try:
        consts, root = parse_text(src)
        ev = Evaluator(consts)
        result = ev.eval_root(root)
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        return 2

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return 0
