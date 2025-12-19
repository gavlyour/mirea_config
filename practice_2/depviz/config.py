from dataclasses import dataclass, asdict
from typing import Optional
from .validators import (
    validate_package_name,
    validate_repo_mode,
    validate_repo,
    validate_debian_version,  # <-- обновлено
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
        pkg = validate_package_name(args.package)
        mode = validate_repo_mode(args.repo_mode)
        repo = validate_repo(args.repo, mode)
        ver = validate_debian_version(args.version)
        if ver is None:
            raise ConfigError("version", "package version is required at this stage")
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
        data = asdict(self)
        order = ["package", "version", "repo_mode", "repo", "output", "max_depth", "filter_substring"]
        return [f"{k}={'' if data.get(k) is None else data.get(k)}" for k in order]
