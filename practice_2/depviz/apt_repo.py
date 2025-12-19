from __future__ import annotations
import bz2
import gzip
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

try:
    import lzma
except Exception:  # noqa: BLE001
    lzma = None  # lzma may be unavailable

from .errors import DataError

USER_AGENT = "depviz/0.0.2 (+https://example.invalid)"
_CANDIDATE_FILENAMES = ("Packages.xz", "Packages.gz", "Packages.bz2", "Packages")
_POCKETS_SUFFIX = ("", "-updates", "-security", "-backports")


def _is_packages_like_path(path: str) -> bool:
    return path.endswith("/Packages") or path.endswith("/Packages.gz") or path.endswith("/Packages.xz") or path.endswith("/Packages.bz2")


def _http_get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read()


def _decompress_by_suffix(url: str, data: bytes) -> bytes:
    url_l = url.lower()
    if url_l.endswith(".xz"):
        if lzma is None:
            raise DataError("repo", "LZMA/XZ support is not available; cannot read Packages.xz")
        return lzma.decompress(data)
    if url_l.endswith(".gz"):
        return gzip.decompress(data)
    if url_l.endswith(".bz2"):
        return bz2.decompress(data)
    return data  # uncompressed


def _iter_control_paragraphs(text: str) -> Iterable[Dict[str, str]]:
    """
    Parse Debian control-like file into dict entries (RFC822-style).
    Continuation lines start with space or tab.
    """
    entry: Dict[str, str] = {}
    last_key: Optional[str] = None

    # normalize newlines
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw_line.strip():
            if entry:
                yield entry
                entry = {}
                last_key = None
            continue
        if raw_line[0] in " \t" and last_key:
            entry[last_key] += "\n" + raw_line[1:]
            continue
        if ":" not in raw_line:
            continue  # skip malformed
        key, value = raw_line.split(":", 1)
        key = key.strip()
        entry[key] = value.lstrip()
        last_key = key
    if entry:
        yield entry


def _parse_dep_field(dep_str: str) -> List[List[str]]:
    """
    Parse Debian Depends/Pre-Depends into list of alternative groups.
    "A (>=1), B | C" -> [["A (>= 1)"], ["B", "C"]]
    """
    result: List[List[str]] = []
    if not dep_str:
        return result
    groups = [g.strip() for g in dep_str.split(",") if g.strip()]
    for g in groups:
        alts = [a.strip() for a in g.split("|") if a.strip()]
        cleaned: List[str] = []
        for a in alts:
            if " " in a:
                pkg, rest = a.split(" ", 1)
                base = pkg.split(":")[0]
                cleaned.append(f"{base} {rest}".strip())
            else:
                base = a.split(":")[0]
                cleaned.append(base)
        result.append(cleaned)
    return result


def _format_dep_groups(groups: List[List[str]]) -> List[str]:
    return [" | ".join(group) for group in groups if group]


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else url + "/"


def _candidate_dirs_across_pockets(dir_url: str) -> List[str]:
    """
    If dir_url looks like .../dists/<pocket>/<component>/binary-<arch>/,
    generate same path across pockets: <pocket>, <pocket>-updates, -security, -backports.
    The original dir_url goes first. Duplicates removed preserving order.
    Otherwise return [dir_url].
    """
    parsed = urlparse(_ensure_trailing_slash(dir_url))
    path = parsed.path
    parts = path.strip("/").split("/")

    try:
        di = parts.index("dists")
    except ValueError:
        return [dir_url]  # not a standard APT dists path

    # Expect .../dists/<pocket>/<component>/binary-<arch>/
    if len(parts) < di + 4:
        return [dir_url]
    pocket = parts[di + 1]
    component = parts[di + 2]
    binary_dir = parts[di + 3]
    if not binary_dir.startswith("binary-"):
        return [dir_url]

    out: List[str] = []
    seen = set()

    def push(pocket_name: str):
        new_parts = parts.copy()
        new_parts[di + 1] = pocket_name
        new_path = "/" + "/".join(new_parts) + "/"
        new_url = urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))
        if new_url not in seen:
            seen.add(new_url)
            out.append(new_url)

    # original pocket and its variants
    for suf in _POCKETS_SUFFIX:
        pocket_name = pocket.split("-")[0] + suf if suf else pocket
        push(pocket_name)

    return out or [dir_url]


def _candidate_package_index_urls(base_url: str) -> List[str]:
    """
    Produce a list of candidate Packages* URLs to try.
    If base_url points to Packages*, return just that.
    If base_url is a directory, try across pockets (when path matches /dists/...),
    and for each directory try Packages.xz, .gz, .bz2, and uncompressed.
    """
    parsed = urlparse(base_url)
    if _is_packages_like_path(parsed.path):
        return [base_url]

    # Treat as directory
    dirs = _candidate_dirs_across_pockets(base_url)
    urls: List[str] = []
    for d in dirs:
        d = _ensure_trailing_slash(d)
        for fn in _CANDIDATE_FILENAMES:
            urls.append(d + fn)
    return urls


def fetch_direct_dependencies(repo_url: str, package: str, version: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Try multiple Packages indexes derived from repo_url (including across pockets).
    Return direct dependencies (Depends + Pre-Depends) for exact package+version match.
    """
    pr = urlparse(repo_url)
    if pr.scheme not in {"http", "https"} or not pr.netloc:
        raise DataError("repo", "expected an HTTP(S) repository URL pointing to a Packages file or a directory")

    tried_indexes: List[str] = []
    last_fetch_error: Optional[str] = None

    for cand in _candidate_package_index_urls(repo_url):
        try:
            raw = _http_get(cand)
            text = _decompress_by_suffix(cand, raw).decode("utf-8", errors="replace")
        except Exception as e:  # network/decompress error — move to next candidate
            last_fetch_error = f"{type(e).__name__}: {e}"
            tried_indexes.append(cand + " (fetch failed)")
            continue

        tried_indexes.append(cand)
        # Scan this index
        matched_entry: Optional[Dict[str, str]] = None
        for entry in _iter_control_paragraphs(text):
            if entry.get("Package") == package and entry.get("Version") == version:
                matched_entry = entry
                break

        if matched_entry:
            depends_str = matched_entry.get("Depends", "").strip()
            predepends_str = matched_entry.get("Pre-Depends", "").strip()
            groups: List[List[str]] = []
            groups += _parse_dep_field(depends_str)
            groups += _parse_dep_field(predepends_str)
            deps_lines = _format_dep_groups(groups)
            return deps_lines, matched_entry

    # Not found anywhere we looked
    tried_str = "\n  - ".join(tried_indexes) if tried_indexes else "(no candidates)"
    hint = ""
    if last_fetch_error and not tried_indexes:
        hint = f" Last error: {last_fetch_error}"
    raise DataError(
        "package",
        f"package {package!r} with version {version!r} not found in any Packages index derived from the provided URL.\n"
        f"Tried:\n  - {tried_str}{hint}",
    )
