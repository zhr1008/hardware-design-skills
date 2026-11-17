"""Install this release's complete, sibling-directory skill bundle."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def inspect(path: Path) -> os.stat_result | None:
    try:
        result = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(result.st_mode) or getattr(result, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"目录或文件经过符号链接或重解析点 {path}")
    return result


def directory_info(path: Path) -> os.stat_result | None:
    result = inspect(path)
    if result is not None and not stat.S_ISDIR(result.st_mode):
        raise ValueError(f"需要目录 {path}")
    return result


def directory_chain(path: Path) -> list[Path]:
    return [*reversed(path.parents), path]


def require_directories(path: Path) -> None:
    for directory in directory_chain(path):
        if directory_info(directory) is None:
            raise ValueError(f"目录不存在 {directory}")


def visible(path: Path) -> bool:
    return not path.name.startswith(".") and path.name != "__pycache__" and path.suffix not in {".pyc", ".pyo"}


def snapshot(root: Path) -> dict[Path, str | None]:
    """Collect relative directories and exact file contents for comparison."""
    entries: dict[Path, str | None] = {}
    pending = [root]
    while pending:
        for path in sorted(filter(visible, pending.pop().iterdir())):
            info = inspect(path)
            if info is None:
                raise ValueError(f"检查期间文件消失 {path}")
            relative = path.relative_to(root)
            if stat.S_ISDIR(info.st_mode):
                entries[relative] = None
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                with path.open("rb") as handle:
                    entries[relative] = hashlib.file_digest(handle, "sha256").hexdigest()
            else:
                raise ValueError(f"不支持的文件类型 {path}")
    return entries


def plan_installation(
    source: Path, target: Path,
) -> tuple[dict[str, dict[Path, str | None]], list[str]]:
    require_directories(source)
    for path in directory_chain(target):
        directory_info(path)
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("请为安装选择与技能包目录分开的目标")

    bundle: dict[str, dict[Path, str | None]] = {}
    for skill in sorted(filter(visible, source.iterdir())):
        if directory_info(skill) is None:
            raise ValueError(f"技能目录消失 {skill.name}")
        files = snapshot(skill)
        if files.get(Path("SKILL.md")) is None:
            raise ValueError(f"技能目录缺少 SKILL.md {skill.name}")
        bundle[skill.name] = files
    if not bundle:
        raise ValueError("技能包不包含可安装的技能")

    pending = {}
    identical = []
    conflicts = []
    for name, entries in bundle.items():
        destination = target / name
        try:
            if directory_info(destination) is None:
                pending[name] = entries
            elif snapshot(destination) == entries:
                identical.append(name)
            else:
                conflicts.append(name)
        except ValueError:
            conflicts.append(name)
    if conflicts:
        raise ValueError(f"目标已存在且有冲突，请选择其他目标目录或处理现有安装。冲突技能 {'、'.join(conflicts)}")
    return pending, identical


def install(source: Path, target: Path, pending: dict[str, dict[Path, str | None]]) -> None:
    created: list[tuple[Path, os.stat_result]] = []

    def create_directory(path: Path) -> None:
        path.mkdir()
        created.append((path, path.lstat()))

    try:
        for path in directory_chain(target):
            if directory_info(path) is None:
                create_directory(path)
        for name, entries in pending.items():
            destination = target / name
            require_directories(destination.parent)
            create_directory(destination)
            for relative, digest in entries.items():
                output = destination / relative
                require_directories(output.parent)
                if digest is None:
                    create_directory(output)
                    continue
                input_path = source / name / relative
                require_directories(input_path.parent)
                info = inspect(input_path)
                if info is None or not stat.S_ISREG(info.st_mode):
                    raise ValueError(f"安装期间源文件改变 {name}/{relative}")
                copied = hashlib.sha256()
                with input_path.open("rb") as reader, output.open("xb") as writer:
                    created.append((output, os.fstat(writer.fileno())))
                    for block in iter(lambda: reader.read(1024 * 1024), b""):
                        writer.write(block)
                        copied.update(block)
                if copied.hexdigest() != digest:
                    raise ValueError(f"安装期间源文件内容改变 {name}/{relative}")
                if os.name != "nt" and info.st_mode & 0o111:
                    output.chmod(stat.S_IMODE(output.stat().st_mode) | (info.st_mode & 0o111))
    except (OSError, ValueError):
        for path, initial in reversed(created):
            try:
                require_directories(path.parent)
                current = inspect(path)
                if current is None:
                    continue
                if (current.st_dev, current.st_ino) != (initial.st_dev, initial.st_ino):
                    raise ValueError("路径已改变")
                if stat.S_ISDIR(initial.st_mode):
                    path.rmdir()
                else:
                    path.unlink()
            except (OSError, ValueError):
                print(f"请检查未清理的本次安装路径 {path}", file=sys.stderr)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.home() / ".agents" / "skills")
    parser.add_argument("--dry-run", action="store_true", help="仅检查安装计划")
    args = parser.parse_args()
    source = absolute(Path(__file__)).parents[1] / "skills"
    target = absolute(args.target)
    try:
        pending, identical = plan_installation(source, target)
        if pending and not args.dry_run:
            install(source, target, pending)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    verb = "计划安装" if args.dry_run else "已安装"
    print(f"{verb} {len(pending)} 项，相同且跳过 {len(identical)} 项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
