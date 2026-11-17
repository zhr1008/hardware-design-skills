"""Check the exact publication tree without echoing matched values."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import zlib


PRIVATE_NAMES = {
    ".codex-install-source.json", ".git", ".netrc", "_netrc", ".npmrc",
    ".pypirc", "credentials", "credentials.json", "id_rsa", "id_ed25519",
    "known_hosts", "kubeconfig", "suppliers.json", "suppliers.local.json",
    "mcp.local.json",
}
PRIVATE_DIRS = {
    ".codex", ".git", ".idea", ".playwright-mcp", ".ssh", ".venv",
    "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "logs",
}
PRIVATE_SUFFIXES = {
    ".key", ".pem", ".p12", ".pfx", ".kdbx", ".sqlite", ".sqlite3", ".db",
    ".db3", ".log", ".bak", ".tmp", ".pyc", ".pyo", ".whl", ".zip", ".rar",
    ".7z", ".tar", ".gz", ".tgz", ".bundle", ".exe", ".dll", ".msi", ".pdb",
    ".bin", ".elf", ".hex", ".uf2",
}
ENGINEERING_SUFFIXES = {
    ".schdoc", ".pcbdoc", ".prjpcb", ".prjpcbstructure", ".schlib", ".pcblib",
    ".intlib", ".libpkg", ".kicad_pcb", ".kicad_pro", ".kicad_sch",
    ".kicad_prl", ".kicad_mod", ".epro", ".elibz", ".elibz2", ".eprj",
    ".ger", ".gbr", ".drl", ".odb", ".sldasm", ".sldprt", ".slddrw",
    ".fcstd", ".step", ".stp", ".stl", ".iges", ".igs", ".ms14",
    ".ms13", ".raw", ".asc", ".uvproj", ".uvprojx", ".ewp", ".eww", ".ioc",
}
PUBLICATION_DIAGRAM = "docs/architecture/hardware-design-skills.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DIAGRAM_BYTES = 8 * 1024 * 1024
MAX_DIAGRAM_AXIS = 4096
PATTERNS = {
    "absolute-home-path": re.compile(
        r"""(?ix)(?:[A-Z]:[/\\]+(?:users|documents[ ]and[ ]settings|home)[/\\]+
        (?!public(?:[/\\]|$)|default(?:[/\\]|$))[^/\\\s"'<>]+
        |(?:(?<![A-Z0-9_./-])|(?<=file://))/(?:home|Users)/
        (?!runner(?:/|$)|Shared(?:/|$))[A-Za-z0-9_.-]+(?=/|[\s"'<>]|$))"""
    ),
    "private-workspace-path": re.compile(
        r"(?i)\b[A-Z]:[/\\]+(?:save[/\\]+(?:code|projects?)|工作|私有|内部|公司)[/\\]+"
    ),
    "network-share": re.compile(
        r"""(?<!\\)\\{2,4}[A-Za-z0-9_][A-Za-z0-9_.-]*\\{1,4}[^\\/"'<>\x60\s]+
        |(?<![:\w/])//[A-Za-z0-9_][A-Za-z0-9_.-]+/[^/"'<>\x60\s]+""",
        re.VERBOSE,
    ),
    "private-hostname": re.compile(
        r"(?i)\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:lan|internal|corp|intra|local)"
        r"(?=:\d|[/\\]|[,\s\"'<>)\]}]|$)"
    ),
    "private-key": re.compile(r"-----BEGIN (?:[A-Z0-9-]+ )*PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "openai-token": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "google-api-key": re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    "vendor-token": re.compile(
        r"\b(?:xox[baprs]-[A-Za-z0-9-]{20,}|glpat-[A-Za-z0-9_-]{20,}|"
        r"npm_[A-Za-z0-9]{30,}|pypi-[A-Za-z0-9_-]{50,}|"
        r"(?:sk|rk)_live_[A-Za-z0-9]{16,}|hf_[A-Za-z0-9]{30,})\b"
    ),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{12,}\b"),
    "credentials-in-url": re.compile(r"(?i)\b(?:https?|ftp|wss?)://[^/@\s:]+:[^/@\s]+@"),
}
EMAIL = re.compile(r"(?i)\b[a-z0-9][a-z0-9_.+-]*@[a-z0-9][a-z0-9.-]*\.[a-z]{2,}\b")
DOCUMENT_DOMAINS = {"example.com", "example.org", "example.net", "example.invalid"}
PUBLIC_ROLE_EMAILS = {"git@github.com", "noreply@github.com"}
SECRET_NAME = (
    r"(?:[A-Z0-9]+[_-])*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"auth[_-]?token|client[_-]?secret|secret[_-]?key|password|passwd|pwd|cookie)"
)
QUOTED_SECRET = re.compile(
    rf"""(?i)(?<!["']\.)\b{SECRET_NAME}["']?\s*[:=]\s*(["'])([^"'\r\n]+)\1"""
)
SHELL_SECRET = re.compile(rf"(?i)\b(?:export|set)\s+({SECRET_NAME})\s*=\s*([-\w+/=.$]{{6,}})")
AUTH_LITERAL = re.compile(
    r"""(?i)\bauthorization["']?\s*[:=]\s*["']?(?:bearer|basic)\s+([A-Z0-9_.+/-]{12,}={0,2})"""
)
SECRET_QUERY = re.compile(
    r"""(?i)\bhttps?://[^\s"'<>]*?[?&](?:access_token|api[_-]?key|signature|secret|session|token)="""
    r"""([A-Z0-9_%.+/-]{12,})"""
)
SECRET_PLACEHOLDER = re.compile(
    r"(?i)(?:<[^<>]+>|\$\{[^{}]+\}|\$[A-Z_][A-Z0-9_]*|%[A-Z_][A-Z0-9_]*%|"
    r"(?:your|example|demo|dummy|test|fake|sample|placeholder|replace|changeme|redacted)"
    r"(?:[-_ ].*)?|(?:x|\*|\.|\u2026)+)"
)
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
IPV6 = re.compile(r"(?i)(?<![0-9A-F:])(?:f[cd][0-9a-f]{2}|fe[89ab][0-9a-f])[:0-9a-f]+")
PRIVATE_NETWORKS = (
    ipaddress.IPv4Network((0x0A000000, 8)),
    ipaddress.IPv4Network((0xAC100000, 12)),
    ipaddress.IPv4Network((0xC0A80000, 16)),
    ipaddress.IPv4Network((0xA9FE0000, 16)),
    ipaddress.IPv6Network((0xFC00 << 112, 7)),
    ipaddress.IPv6Network((0xFE80 << 112, 10)),
)


def public_email(value: str) -> bool:
    value = value.casefold()
    domain = value.rsplit("@", 1)[-1]
    return (value in PUBLIC_ROLE_EMAILS or domain == "users.noreply.github.com"
            or domain in DOCUMENT_DOMAINS or domain.endswith(
                (".example.com", ".example.org", ".example.net", ".example", ".invalid", ".test")))


def local_address(token: str) -> bool:
    try:
        address = ipaddress.ip_address(token)
    except ValueError:
        return False
    return any(address.version == network.version and address in network for network in PRIVATE_NETWORKS)


def has_secret_value(value: str) -> bool:
    return len(value.strip()) >= 6 and SECRET_PLACEHOLDER.fullmatch(value.strip()) is None


def content_findings(content: bytes):
    try:
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            source = content.decode("utf-16")
        else:
            source = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        yield 0, "binary-or-unsupported-text-encoding"
        return
    if "\x00" in source:
        yield 0, "binary-or-unsupported-text-encoding"
        return
    for number, line in enumerate(source.splitlines(), 1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                yield number, name
        if (any(local_address(item.group()) for item in IPV4.finditer(line))
                or any(local_address(item.group()) for item in IPV6.finditer(line))):
            yield number, "private-network-address"
        if any(not public_email(item.group()) for item in EMAIL.finditer(line)):
            yield number, "email-requires-review"
        if (any(has_secret_value(item.group(2)) for item in QUOTED_SECRET.finditer(line))
                or any(has_secret_value(item.group(2)) for item in SHELL_SECRET.finditer(line))):
            yield number, "credential-literal"
        if (any(has_secret_value(item.group(1)) for item in AUTH_LITERAL.finditer(line))
                or any(has_secret_value(item.group(1)) for item in SECRET_QUERY.finditer(line))):
            yield number, "authorization-or-url-secret"


def valid_publication_diagram(content: bytes) -> bool:
    """Accept the generated diagram's PNG format without ancillary data."""
    if len(content) > MAX_DIAGRAM_BYTES or not content.startswith(PNG_SIGNATURE):
        return False

    offset = len(PNG_SIGNATURE)
    scanline_bytes = height = 0
    compressed = bytearray()
    while offset + 12 <= len(content):
        length, kind = struct.unpack_from(">I4s", content, offset)
        end = offset + 12 + length
        if end > len(content):
            return False
        crc = struct.unpack_from(">I", content, end - 4)[0]
        if zlib.crc32(content[offset + 4:end - 4]) != crc:
            return False
        data = content[offset + 8:end - 4]

        if offset == len(PNG_SIGNATURE):
            if kind != b"IHDR" or length != 13:
                return False
            width, height, depth, color, compression, filters, interlace = struct.unpack(">IIBBBBB", data)
            if (not 1 <= width <= MAX_DIAGRAM_AXIS or not 1 <= height <= MAX_DIAGRAM_AXIS
                    or depth != 8 or color not in {2, 6} or (compression, filters, interlace) != (0, 0, 0)):
                return False
            scanline_bytes = 1 + width * (3 if color == 2 else 4)
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            if length != 0 or end != len(content) or not compressed:
                return False
            expected = scanline_bytes * height
            decoder = zlib.decompressobj()
            try:
                pixels = decoder.decompress(compressed, expected + 1)
            except zlib.error:
                return False
            return (len(pixels) == expected and decoder.eof and not decoder.unused_data
                    and not decoder.unconsumed_tail and all(value <= 4 for value in pixels[::scanline_bytes]))
        else:
            # The source renderer emits only IHDR, IDAT and IEND for this diagram.
            return False
        offset = end
    return False


def path_findings(name: str):
    path = PurePosixPath(name.casefold())
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        yield "nonportable-path"
    if any(folder in PRIVATE_DIRS for folder in path.parts[:-1]):
        yield "private-directory"
    if any(path.parts[i:i + 2] == ("sources", "raw") for i in range(len(path.parts) - 1)):
        yield "raw-source-corpus"
    if (path.name in PRIVATE_NAMES or path.name.startswith(("client_secret", ".env"))
            and path.name not in {".env.example", ".env.template"}):
        yield "private-metadata-or-credential-file"
    if path.suffix in ENGINEERING_SUFFIXES:
        yield "native-engineering-artifact"
    elif path.suffix in PRIVATE_SUFFIXES:
        yield "local-artifact-or-archive"


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(repo), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


def git_entries(repo: Path, tree: str | None):
    if tree:
        raw = git(repo, "ls-tree", "-r", "-z", tree)
        for entry in raw.split(b"\0"):
            if entry:
                header, name = entry.split(b"\t", 1)
                mode, _, oid = header.decode("ascii").split()
                yield mode, oid, name.decode("utf-8"), False
        return
    for entry in git(repo, "ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            header, name = entry.split(b"\t", 1)
            mode, oid, stage = header.decode("ascii").split()
            yield mode, oid, name.decode("utf-8"), stage != "0"


def remaining_objects(repo: Path, entries):
    if not entries:
        return
    payload = "".join(f"{oid}\n" for _, oid in entries).encode("ascii")
    raw = git(repo, "cat-file", "--batch", data=payload)
    offset = 0
    for name, oid in entries:
        end = raw.index(b"\n", offset)
        actual_oid, kind, length = raw[offset:end].split()
        if actual_oid.decode("ascii") != oid or kind != b"blob":
            raise ValueError("Unexpected object in publication tree")
        start = end + 1
        offset = start + int(length) + 1
        yield name, raw[start:offset - 1]


def working_content(repo: Path, name: str) -> bytes:
    current = repo
    for component in PurePosixPath(name).parts:
        current /= component
        info = current.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise ValueError("Live path is a symbolic link or reparse point")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Live path is not a regular file")
    return current.read_bytes()


def scan(repo: Path, *, staged: bool, tree: str | None):
    findings = []
    entries = []
    for mode, oid, name, unmerged in git_entries(repo, tree):
        reasons = list(path_findings(name))
        filename_findings = [f"filename-{rule}" for _, rule in content_findings(name.encode("utf-8"))]
        reasons.extend(filename_findings)
        if unmerged:
            reasons.append("unmerged-index")
        if mode not in {"100644", "100755"}:
            reasons.append("symlink-or-submodule")
        if reasons:
            reported_name = "[redacted filename]" if filename_findings else name
            findings.extend({"path": reported_name, "line": 0, "rule": rule} for rule in reasons)
        else:
            entries.append((name, oid))
    if not entries and not findings:
        return 0, [{"path": ".", "line": 0, "rule": "empty-publication-tree"}]

    if staged or tree:
        content = remaining_objects(repo, entries)
    else:
        def worktree():
            for name, _ in entries:
                try:
                    raw = working_content(repo, name)
                except (OSError, ValueError):
                    findings.append({"path": name, "line": 0, "rule": "missing-or-nonregular-worktree-path"})
                else:
                    yield name, raw
        content = worktree()

    checked = 0
    for name, raw in content:
        if name == PUBLICATION_DIAGRAM:
            if not valid_publication_diagram(raw):
                findings.append({"path": name, "line": 0, "rule": "invalid-publication-diagram-png"})
        else:
            findings.extend({"path": name, "line": line, "rule": rule}
                            for line, rule in content_findings(raw))
        checked += 1
    return checked, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="Scan the Git index blob contents.")
    mode.add_argument("--tree", metavar="REF", help="Scan the committed tree of a Git ref.")
    args = parser.parse_args()
    try:
        tree = (git(args.repo, "rev-parse", "--verify", "--end-of-options", args.tree + "^{tree}")
                .decode("ascii").strip() if args.tree else None)
        scanned, findings = scan(args.repo, staged=args.staged, tree=tree)
    except (OSError, ValueError, subprocess.SubprocessError):
        scanned, findings = 0, [{"path": ".", "line": 0, "rule": "unable-to-read-publication-tree"}]
    print(json.dumps({"files_checked": scanned, "findings": findings}, ensure_ascii=False, indent=2))
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
