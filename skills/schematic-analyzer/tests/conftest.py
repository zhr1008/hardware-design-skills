"""Run the bundled tests from any install path; external board fixtures are explicit."""
import os
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))
DATA_ROOT = Path(os.environ.get("SCHEMATIC_ANALYZER_TEST_DATA", str(SKILL_ROOT / "tests" / "fixtures")))


@pytest.fixture(autouse=True)
def installed_test_paths(request, monkeypatch):
    """Keep original tests/assertions; only replace upstream's hardcoded checkout paths."""
    module = request.module
    replacements = {
        "REPO_ROOT": SKILL_ROOT,
        "SCRIPTS_ROOT": SCRIPTS_ROOT,
        "CLI_PATH": SCRIPTS_ROOT / "schematic-cli.py",
        "DENALI_DIR": DATA_ROOT / "denali",
        "DENALI_ROOT": DATA_ROOT / "denali" / "RK3576.kicad_sch",
        "E1005_ROOT": DATA_ROOT / "E1005_v01",
    }
    for name, value in replacements.items():
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)
    referenced = set(request.function.__code__.co_names)
    for name in ("DENALI_DIR", "DENALI_ROOT", "E1005_ROOT"):
        if name in referenced and not replacements[name].exists():
            pytest.skip(f"External upstream board fixture unavailable: {name}; set SCHEMATIC_ANALYZER_TEST_DATA")
