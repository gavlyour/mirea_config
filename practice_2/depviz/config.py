from dataclasses import dataclass, asdict
from typing import Optional
from .validators import (
    validate_package_name,
    validate_repo_mode,
    validate_repo,
    validate_version,
    validate_output_filename,
    validate_max_depth,
    validate_filter_substring,
)
from .errors import ConfigError

@dataclass(frozen=True)
class Config:
    package: str
    repo: str
    repo_mode: str
    version: Optional[str]
    output: str
    max_depth: int
    filter_substring: Optional[str]

    @classmethod
    def from_args(cls, args: "argparse.Namespace") -> "Config":
        # Валидируем последовательно, чтобы демонстрировать ошибки для каждого поля
        pkg = validate_package_name(args.package)
        mode = validate_repo_mode(args.repo_mode)
        repo = validate_repo(args.repo, mode)
        ver = validate_version(args.version)
        out = validate_output_filename(args.output)
        depth = validate_max_depth(args.max_depth)
        flt = validate_filter_substring(args.filter)
        return cls(
            package=pkg,
            repo=repo,
            repo_mode=mode,
            version=ver,
            output=out,
            max_depth=depth,
            filter_substring=flt,
        )

    def to_kv_lines(self) -> list[str]:
        # Выгрузить только настраиваемые поля в формате ключ=значение
        data = asdict(self)
        # Чёткий порядок вывода
        order = ["package", "version", "repo_mode", "repo", "output", "max_depth", "filter_substring"]
        lines = []
        for key in order:
            val = data.get(key)
            # None выводим как пустую строку для консистентности
            lines.append(f"{key}={'' if val is None else val}")
        return lines
