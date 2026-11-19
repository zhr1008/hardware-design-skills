"""Inspect local backend capabilities without starting persistent services or opening designs."""

import argparse
from datetime import datetime
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

from evidence_adapter import strict_json
from hardware_tool import local_file


HARDWARE = Path(__file__).resolve().parents[1]


def run(arguments, cwd=None):
    try:
        return subprocess.run(
            arguments, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_head(directory):
    git = shutil.which("git")
    if git and (directory / ".git").exists():
        result = run([git, "-C", str(directory), "rev-parse", "HEAD"])
        if result and result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", result.stdout.strip()):
            return result.stdout.strip()
    return None


def distribution_version(distribution):
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def observed_mcp(contract, observation):
    if not observation:
        return {}
    if not isinstance(observation, dict) or set(observation) - {"tools", "read_only_call", "observed_at"}:
        raise ValueError("components 运行时观测字段无效")
    observed_at = observation.get("observed_at")
    if not isinstance(observed_at, str) or datetime.fromisoformat(observed_at).utcoffset() is None:
        raise ValueError("components 运行时观测需要带时区的 observed_at")
    tools = observation.get("tools")
    if not isinstance(tools, dict):
        raise ValueError("components 运行时观测需要 tools 快照")
    name = contract["required_tool"]
    schema = tools.get(name)
    if schema is not None and not isinstance(schema, dict):
        raise ValueError("components 工具签名需要 JSON 对象")
    properties = schema.get("properties") if schema else None
    required = schema.get("required", []) if schema else []
    compatible = (
        isinstance(properties, dict) and isinstance(required, list)
        and all(isinstance(key, str) for key in required)
        and sorted(required) == sorted(contract["required_arguments"])
        and all(isinstance(properties.get(key), dict) and properties[key].get("type") == expected
                for key, expected in contract["required_parameters"].items())
    )
    digest = None
    if schema is not None:
        digest = hashlib.sha256(json.dumps(
            schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
    receipt = observation.get("read_only_call")
    if receipt is not None and (
        not isinstance(receipt, dict) or set(receipt) != {"tool", "status", "input_schema_sha256"}
        or receipt["status"] not in ("success", "failed")
    ):
        raise ValueError("components 只读调用回执字段无效")
    return {
        "connected": True,
        "call_verified": None if receipt is None else bool(
            compatible and receipt["tool"] == name and receipt["status"] == "success"
            and receipt["input_schema_sha256"] == digest
        ),
        "contract_compatible": compatible,
        "input_schema_sha256": digest,
        "observation_source": "provided_runtime_snapshot",
        "observed_at": observed_at,
        "current_session_probed": False,
    }


def inspect_backend(name, contract, cli, observations):
    status = {
        "declared": True, "installed": None, "connected": None, "call_verified": None,
        "version": None, "contract_compatible": None,
        "scope": contract["scope"], "probe_scope": contract["probe_scope"],
        "probe_side_effect": contract["probe_side_effect"],
    }
    if contract["kind"] == "local_cli":
        if name in cli:
            command = cli[name] if Path(cli[name]).is_file() else None
        else:
            command = next((path for executable in contract["executables"] if (path := shutil.which(executable))), None)
        status["installed"] = bool(command)
        if command:
            result = run([command, *contract["version_command"]])
            status.update(connected=result is not None, call_verified=bool(result and result.returncode == 0))
            if status["call_verified"]:
                output = result.stdout.strip() or result.stderr.strip()
                found = re.search(r"(?im)^\s*(?:\*{2}\s*)?ngspice-([0-9]+(?:\.[0-9]+)*)", output)
                if name == "ngspice" and found:
                    status["version"] = found[1]
                elif name == "kicad-cli" and output:
                    status["version"] = output.splitlines()[0].strip()
                if "accepted_version" in contract:
                    status["contract_compatible"] = bool(
                        re.fullmatch(contract["accepted_version"], status["version"] or "")
                    )
        return status
    package = distribution_version(contract["distribution"])
    status.update(installed=package is not None, version=package)
    if name == "components":
        status.update(observed_mcp(contract, observations.get(name)))
    return status


def main():
    contracts = strict_json((HARDWARE / "assets/backend-contracts.json").read_bytes())["backends"]
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--backend", choices=list(contracts), action="append")
    parser.add_argument("--kicad-cli")
    parser.add_argument("--ngspice-cli")
    parser.add_argument("--sourcing-repo", type=Path)
    parser.add_argument("--runtime-observation")
    args = parser.parse_args()
    observations = {}
    try:
        if args.runtime_observation:
            source = strict_json(local_file(args.runtime_observation).read_bytes())
            if (not isinstance(source, dict) or set(source) != {"schema", "backends"}
                    or source["schema"] != "hardware-runtime-observation-v1"
                    or not isinstance(source["backends"], dict) or set(source["backends"]) - {"components"}):
                raise ValueError("不支持的后端运行时观测合同")
            observations = source["backends"]
        cli = {name: str(local_file(path, input_file=False)) for name, path in (
            ("kicad-cli", args.kicad_cli), ("ngspice", args.ngspice_cli),
        ) if path}
        backends = {name: inspect_backend(name, contracts[name], cli, observations)
                    for name in dict.fromkeys(args.backend or contracts)}
        repository = HARDWARE.parents[1]
        bundled_version = repository / "VERSION"
        versions = {
            "hardware_design_skills": {
                "version": bundled_version.read_text(encoding="utf-8").strip() if bundled_version.is_file() else None,
                "git_commit": git_head(repository),
            },
            "component_sourcing_mcp": {
                "version": distribution_version(contracts["components"]["distribution"]),
                "git_commit": None,
            },
        }
        if args.sourcing_repo:
            metadata = local_file(args.sourcing_repo / "pyproject.toml")
            project = tomllib.loads(metadata.read_text(encoding="utf-8"))["project"]
            if project["name"] != contracts["components"]["distribution"]:
                raise ValueError("--sourcing-repo 需要 component-sourcing-mcp 仓库")
            versions["component_sourcing_mcp"].update(
                source_version=project.get("version"), git_commit=git_head(metadata.parent),
            )
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"诊断输入无效：{error}\n")
    print(json.dumps({
        "schema": "hardware-backend-doctor-v1",
        "repositories": versions,
        "backends": backends,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
