"""Validate skill metadata, relative documentation links and Python syntax."""

import re
from pathlib import Path
from sys import exit
from urllib.parse import unquote

import yaml


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^]\n]+\]\(([^)\n]+)\)")
FRONTMATTER = re.compile(r"\A---\n(.*?)^---[ \t]*$", re.MULTILINE | re.DOTALL)
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class MetadataLoader(yaml.SafeLoader):
    """Reject ambiguous keys instead of silently using the last value."""

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            keys = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str) or key in keys:
                    raise yaml.YAMLError("metadata keys must be unique strings")
                keys.add(key)
        return super().construct_mapping(node, deep=deep)


def check_skill(skill):
    entry = skill / "SKILL.md"
    if not entry.is_file():
        yield f"{skill.name}: missing SKILL.md"
        return
    match = FRONTMATTER.match(entry.read_text(encoding="utf-8-sig"))
    if match is None:
        yield f"{skill.name}: missing YAML frontmatter with line-delimited markers"
        return
    try:
        metadata = yaml.load(match[1], Loader=MetadataLoader)
    except yaml.YAMLError:
        yield f"{skill.name}: invalid SKILL.md YAML or duplicate metadata key"
        return
    if not isinstance(metadata, dict):
        yield f"{skill.name}: SKILL.md frontmatter must be a mapping"
        return
    name = metadata.get("name")
    description = metadata.get("description")
    if name != skill.name or len(skill.name) > 64 or SKILL_NAME.fullmatch(skill.name) is None:
        yield f"{skill.name}: name must match the skill directory and use lowercase hyphen-case (1–64 characters)"
    if (not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024
            or "<" in description or ">" in description or description.strip().startswith("[TODO:")):
        yield f"{skill.name}: description must be a complete string (1–1024 characters, no angle brackets)"

    agent = skill / "agents" / "openai.yaml"
    if agent.is_file():
        try:
            config = yaml.load(agent.read_text(encoding="utf-8-sig"), Loader=MetadataLoader)
        except yaml.YAMLError:
            yield f"{skill.name}: invalid agents/openai.yaml YAML or duplicate metadata key"
            return
        if not isinstance(config, dict):
            yield f"{skill.name}: agents/openai.yaml must be a mapping"
            return
        if "policy" in config:
            policy = config["policy"]
            if (not isinstance(policy, dict)
                    or "allow_implicit_invocation" in policy
                    and not isinstance(policy["allow_implicit_invocation"], bool)):
                yield f"{skill.name}: allow_implicit_invocation must be a YAML boolean inside policy"


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
    issues = [issue for skill in skills for issue in check_skill(skill)]
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
