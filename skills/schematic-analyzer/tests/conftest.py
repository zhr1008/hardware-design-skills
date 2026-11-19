"""Run bundled tests from any install path and stage board inputs in temporary copies."""
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))
DATA_ROOT = Path(os.environ.get("SCHEMATIC_ANALYZER_TEST_DATA", str(SKILL_ROOT / "tests" / "fixtures")))
DENALI_ROOT_NAME = "RK3576.kicad_sch"


@pytest.fixture(autouse=True)
def installed_test_paths(request, monkeypatch):
    """Replace upstream's hardcoded checkout paths for scripts and patterns."""
    module = request.module
    replacements = {
        "REPO_ROOT": SKILL_ROOT,
        "SCRIPTS_ROOT": SCRIPTS_ROOT,
        "CLI_PATH": SCRIPTS_ROOT / "schematic-cli.py",
    }
    for name, value in replacements.items():
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)


def copy_upstream_board(name: str, destination: Path, *, root_file: str | None = None) -> Path:
    source = DATA_ROOT / name
    expected = source / root_file if root_file else source
    exists = expected.is_file() if root_file else expected.is_dir()
    if not exists:
        if "SCHEMATIC_ANALYZER_TEST_DATA" in os.environ:
            pytest.fail(f"Configured upstream fixture is missing: {expected}")
        pytest.skip(f"External upstream board fixture unavailable: {name}; set SCHEMATIC_ANALYZER_TEST_DATA")
    copy = destination / name
    shutil.copytree(source, copy, ignore=shutil.ignore_patterns(".schematic-analyzer", ".git"))
    return copy / root_file if root_file else copy


@pytest.fixture
def denali_root(tmp_path: Path) -> Path:
    return copy_upstream_board("denali", tmp_path, root_file=DENALI_ROOT_NAME)


@pytest.fixture
def denali_connected_root(denali_root: Path) -> Path:
    if shutil.which("kicad-cli") is None:
        pytest.skip("Denali fixture is available; pin-level connectivity requires kicad-cli on PATH")
    return denali_root


@pytest.fixture
def e1005_root(tmp_path: Path) -> Path:
    return copy_upstream_board("E1005_v01", tmp_path)


@dataclass(frozen=True)
class SchematicExample:
    root: Path
    child_reference: str
    unrelated_sheet: str


@pytest.fixture
def schematic_example(tmp_path: Path) -> SchematicExample:
    if "SCHEMATIC_ANALYZER_TEST_DATA" in os.environ or (DATA_ROOT / "denali" / DENALI_ROOT_NAME).is_file():
        root = copy_upstream_board("denali", tmp_path, root_file=DENALI_ROOT_NAME)
        return SchematicExample(root, "U36", "USB_MUX.kicad_sch")

    root = tmp_path / "Example.kicad_sch"
    child = tmp_path / "IO.kicad_sch"
    unrelated = tmp_path / "Spare.kicad_sch"
    root_id = example_uuid("root")
    sheet_id = example_uuid("io-sheet")
    # Twelve distinct footprints, references and labels cross the ten-result CLI limit.
    root_symbols = "\n".join(example_symbol(index, f"/{root_id}", y=20 + index * 5) for index in range(1, 13))
    root_labels = "\n".join(example_label(index, y=20 + index * 5) for index in range(1, 13))
    sheet = f'''  (sheet
    (at 100 25) (size 40 20)
    (stroke (width 0) (type default)) (fill (color 0 0 0 0))
    (uuid "{sheet_id}")
    (property "Sheetname" "IO" (at 100 24 0) (effects (font (size 1 1))))
    (property "Sheetfile" "{child.name}" (at 100 46 0) (effects (font (size 1 1))))
    (instances (project "Example" (path "/{root_id}" (page "2"))))
  )
  (sheet_instances (path "/" (page "1")))'''
    write_example_page(root, root_id, f"{root_symbols}\n{root_labels}\n{sheet}")
    write_example_page(child, example_uuid("io-page"), example_symbol(13, f"/{root_id}/{sheet_id}", y=30))
    write_example_page(unrelated, example_uuid("spare-page"), "")
    return SchematicExample(root, "U13", unrelated.name)


def example_uuid(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"schematic-analyzer-tests/{name}"))


def write_example_page(path: Path, page_id: str, body: str) -> None:
    path.write_text(
        f'''(kicad_sch (version 20250114) (generator "eeschema")
  (uuid "{page_id}") (paper "A4")
  (lib_symbols
    (symbol "Fixture:TestNode"
      (pin_names (offset 0)) (in_bom yes) (on_board yes)
      (symbol "TestNode_1_1"
        (pin passive line (at 0 0 0) (length 2.54)
          (name "IO" (effects (font (size 1 1))))
          (number "1" (effects (font (size 1 1))))
        )
      )
    )
  )
{body}
)
''',
        encoding="utf-8",
    )


def example_symbol(index: int, sheet_path: str, *, y: int) -> str:
    return f'''  (symbol
    (lib_id "Fixture:TestNode")
    (at 50 {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{example_uuid(f'symbol-{index}')}")
    (property "Reference" "U{index}" (at 50 {y} 0) (effects (font (size 1 1))))
    (property "Value" "Node-{20 - index:02d}" (at 50 {y} 0) (effects (font (size 1 1))))
    (property "Footprint" "Fixture:Footprint-{index:02d}" (at 50 {y} 0) (effects (font (size 1 1))))
    (pin "1" (uuid "{example_uuid(f'pin-{index}')}"))
    (instances (project "Example" (path "{sheet_path}" (reference "U{index}") (unit 1))))
  )'''


def example_label(index: int, *, y: int) -> str:
    return f'''  (label "I2C_{index:02d}_SCL" (at 50 {y} 0)
    (effects (font (size 1 1)) (justify left bottom))
    (uuid "{example_uuid(f'label-{index}')}")
  )'''
