import os
import re
from urllib.parse import urlparse
from .errors import ConfigError

_PKG_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")

# Debian version format (Policy §5.6.12): [epoch:]upstream[-debian]
# epoch: digits+
# upstream: starts with digit; allowed chars [A-Za-z0-9.+:~] (no '-')
# debian: allowed chars [A-Za-z0-9+.~] (no '-')
_DEB_VER_RE = re.compile(
    r"^\s*(?:\d+:)?[0-9][A-Za-z0-9.+:~]*(?:-[A-Za-z0-9+.~]+)?\s*$"
)

_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}

def validate_package_name(name: str) -> str:
    if not name:
        raise ConfigError("package", "package name must not be empty")
    if not _PKG_RE.match(name):
        raise ConfigError(
            "package",
            "invalid package name: allowed letters, digits, ., _, -, and it must not start or end with a special character",
        )
    return name

def validate_repo_mode(mode: str) -> str:
    allowed = {"url", "path"}
    if mode not in allowed:
        raise ConfigError("repo_mode", f"unknown repository mode: {mode!r}. Allowed: {', '.join(sorted(allowed))}")
    return mode

def validate_repo(repo: str, mode: str) -> str:
    if not repo:
        raise ConfigError("repo", "repository URL/path is required")
    if mode == "url":
        pr = urlparse(repo)
        if pr.scheme not in {"http", "https"} or not pr.netloc:
            raise ConfigError("repo", "for 'url' mode, expected an address like https://host/... (Packages* or directory)")
    elif mode == "path":
        if not os.path.exists(repo):
            raise ConfigError("repo", f"path not found: {repo}")
        if not os.path.isfile(repo) and not os.path.isdir(repo):
            raise ConfigError("repo", f"expected a file or directory, got: {repo}")
        if not os.access(repo, os.R_OK):
            raise ConfigError("repo", f"no read permission for: {repo}")
    return repo

def validate_debian_version(version: str | None) -> str | None:
    """Accept Debian/Ubuntu version strings like '7.81.0-1ubuntu1.15', '1:2.0~rc1-0ubuntu1'."""
    if version is None or version == "":
        return None
    if not _DEB_VER_RE.match(version):
        raise ConfigError(
            "version",
            "version does not look like a Debian/Ubuntu version, e.g., '7.81.0-1ubuntu1.15', '1:2.0~rc1-0ubuntu1'",
        )
    return version.strip()

def validate_output_filename(filename: str) -> str:
    if not filename:
        raise ConfigError("output", "output image filename must not be empty")
    root, ext = os.path.splitext(filename)
    if not ext or ext.lower() not in _ALLOWED_IMAGE_EXT:
        raise ConfigError("output", f"extension {ext or '(none)'} is not supported. Allowed: {', '.join(sorted(_ALLOWED_IMAGE_EXT))}")
    parent = os.path.dirname(os.path.abspath(filename)) or "."
    if not os.path.exists(parent):
        raise ConfigError("output", f"directory does not exist: {parent}")
    if not os.access(parent, os.W_OK):
        raise ConfigError("output", f"no write permission to directory: {parent}")
    if root.strip() == "":
        raise ConfigError("output", "invalid output filename (empty base name)")
    return filename

def validate_max_depth(value: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ConfigError("max_depth", f"expected an integer, got: {value!r}")
    if v < 0:
        raise ConfigError("max_depth", "value must not be negative")
    if v > 1000:
        raise ConfigError("max_depth", "value is too large (maximum is 1000)")
    return v

def validate_filter_substring(s: str | None) -> str | None:
    if s is None:
        return None
    if s.strip() == "":
        raise ConfigError("filter", "filter substring must not be empty")
    return s
