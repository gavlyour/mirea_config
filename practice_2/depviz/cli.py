import argparse
import sys
from .config import Config
from .errors import ConfigError, DataError
from .apt_repo import fetch_direct_dependencies

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="depviz",
        description="Dependency graph visualizer (Stage 2: data collection for APT packages).",
    )
    p.add_argument("-p", "--package", required=True, help="Target package name")
    p.add_argument("-r", "--repo", required=True, help="APT repository URL or Packages* file URL / directory URL")
    p.add_argument(
        "--repo-mode",
        choices=["url", "path"],
        required=True,
        help="Repository mode: 'url' (HTTP[S]) or 'path' (local). Stage 2 requires 'url'.",
    )
    p.add_argument(
        "-v", "--version",
        required=False,
        default=None,
        help="Debian/Ubuntu package version, e.g., 7.81.0-1ubuntu1.15 or 1:2.0~rc1-0ubuntu1 (exact match in Packages index)",
    )
    p.add_argument("-o", "--output", default="graph.png", help="Output image filename (png/jpg/jpeg/svg/pdf)")
    p.add_argument("-d", "--max-depth", default=3, type=int, help="Max dependency depth (>= 0). Not used in Stage 2 output.")
    p.add_argument("-f", "--filter", default=None, help="Substring filter for packages (not applied in Stage 2).")
    return p

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = Config.from_args(args)
    except ConfigError as e:
        sys.stderr.write(f"Configuration error [{e.field}]: {e.message}\n")
        return 2

    if cfg.repo_mode != "url":
        sys.stderr.write("Data error [repo_mode]: Stage 2 requires --repo-mode=url to fetch APT metadata over HTTP(S)\n")
        return 3

    for line in cfg.to_kv_lines():
        print(line)

    print("\n# Direct dependencies")
    try:
        deps, _entry = fetch_direct_dependencies(cfg.repo, cfg.package, cfg.version)  # type: ignore[arg-type]
    except DataError as e:
        sys.stderr.write(f"Data error [{e.field}]: {e.message}\n")
        return 3

    if not deps:
        print("(none)")
    else:
        for line in deps:
            print(line)
    return 0
