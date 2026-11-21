"""Exercise offline Altium library readback without shipping native library files."""

from pathlib import Path
import subprocess
import sys

import pytest


CHECKER = (Path(__file__).resolve().parents[1] / "skills" / "altium-library"
           / "scripts" / "check_pin_pad_links.py")


def run(*args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(CHECKER), *map(str, args)],
        capture_output=True, encoding="utf-8", timeout=20, check=False,
    )


def test_help_runs_without_loading_altium_backend():
    result = run("--help")
    assert result.returncode == 0, result.stderr
    assert "--require-step" in result.stdout and "--step-dir" in result.stdout


def test_saved_pairs_distinguish_association_pin_and_step_evidence(tmp_path):
    altium = pytest.importorskip("altium_monkey", reason="optional Altium saved-library backend")
    sch_path = tmp_path / "fixture.SchLib"
    pcb_path = tmp_path / "fixture.PcbLib"
    step_path = tmp_path / "fixture.step"
    # Minimal exchange framing for a byte-level test. It contains no geometry.
    payload = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    sch = altium.AltiumSchLib()
    symbol = sch.add_symbol("CONN")
    symbol.add_pin(altium.AltiumSchPin(designator="1", name="1"))
    symbol.add_pin(altium.AltiumSchPin(designator="2", name="2", y=100))
    symbol.add_footprint("CONN", library_name=pcb_path.name)
    sch.save(sch_path)
    pcb = altium.AltiumPcbLib()
    footprint = pcb.add_footprint("CONN")
    for index, number in enumerate(("1", "3")):
        footprint.add_pad(designator=number, position_mils=(index * 100, 0),
                          width_mils=65, height_mils=65)
    pcb.save(pcb_path)
    failed = run(sch_path, pcb_path)
    assert failed.returncode == 1 and "pin/pad mismatch" in failed.stdout

    footprint.pads[1].designator = "2"
    pcb.save(pcb_path)
    matched = run(sch_path, pcb_path, "--symbol", "conn")
    assert matched.returncode == 0 and "2 pins verified" in matched.stdout
    other_library = tmp_path / "other.PcbLib"
    other_library.write_bytes(pcb_path.read_bytes())
    wrong_library = run(sch_path, other_library)
    assert wrong_library.returncode == 1 and "linked library differs" in wrong_library.stdout
    missing_step = run(sch_path, pcb_path, "--require-step")
    assert missing_step.returncode == 1 and "no embedded STEP" in missing_step.stdout

    model = pcb.add_embedded_model(name=step_path.name, model_data=payload)
    footprint.add_component_body(outline_points_mils=[(-20, -20), (120, -20), (120, 20), (-20, 20)],
                                 overall_height_mils=20, model=model)
    pcb.save(pcb_path)
    step_path.write_bytes(payload)
    with_step = run(sch_path, pcb_path, "--step-dir", tmp_path)
    assert with_step.returncode == 0 and "2 pins verified" in with_step.stdout, with_step.stderr + with_step.stdout
    step_path.write_bytes(payload.replace(b"DATA;", b"DATA; /* changed */"))
    altered = run(sch_path, pcb_path, "--step-dir", tmp_path)
    assert altered.returncode == 1 and "embedded bytes differ" in altered.stdout

    missing_symbol = run(sch_path, pcb_path, "--symbol", "absent")
    assert missing_symbol.returncode == 1 and "symbol not found" in missing_symbol.stdout
    missing_input = run(tmp_path / "absent.SchLib", pcb_path)
    assert missing_input.returncode == 2 and "cannot read library evidence" in missing_input.stderr
