"""Validate skill entry points, relative documentation links and Python syntax."""

import re
from pathlib import Path
from sys import exit
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^]\n]+\]\(([^)\n]+)\)")


def check_links(path, text):
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"\s*(```|~~~)", line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1] == fence:
                fence = None
            continue
        if fence:
            continue
        for match in LINK.finditer(line):
            target = unquote(match[1].split("#", 1)[0].strip("<>"))
            if not target or ":" in target or target.startswith(("/", "~", "...", "\\")):
                continue
            destination = (path.parent / target).resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                yield f"{path.relative_to(ROOT)}:{number} relative link missing: {target}"


def main():
    skills = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
    issues = []
    for skill in skills:
        entry = skill / "SKILL.md"
        if not entry.is_file():
            issues.append(f"{skill.name}: missing SKILL.md")
            continue
        front = entry.read_text(encoding="utf-8-sig").split("---", 2)
        if len(front) != 3 or front[0].strip() or not re.search(rf"(?m)^name:\s*{re.escape(skill.name)}\s*$", front[1]) or not re.search(r"(?m)^description:\s*\S", front[1]):
            issues.append(f"{skill.name}: invalid name or description")
    md_files = [ROOT / "README.md", ROOT / "THIRD_PARTY_NOTICES.md"]
    md_files.extend((ROOT / "docs").rglob("*.md"))
    md_files.extend((ROOT / "skills").rglob("*.md"))
    for path in md_files:
        issues.extend(check_links(path, path.read_text(encoding="utf-8-sig")))
    modules = list((ROOT / "scripts").rglob("*.py")) + list((ROOT / "skills").rglob("*.py"))
    for path in modules:
        try:
            compile(path.read_bytes(), str(path.relative_to(ROOT)), "exec")
        except SyntaxError as exc:
            issues.append(f"{path.relative_to(ROOT)}:{exc.lineno} Python syntax error")
    for issue in issues:
        print(issue)
    print(f"{len(skills)} skills, {len(md_files)} Markdown files, {len(modules)} Python modules, {len(issues)} problems")
    return int(bool(issues))


if __name__ == "__main__":
    exit(main())
