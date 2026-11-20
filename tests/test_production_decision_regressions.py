"""Regression cases for frozen assembly faces and unscaled oscilloscope captures."""

import csv
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_specialist_artifact_guards import (
    PROGRAM_STATE, RELEASE_SCRIPTS, SKILLS, VALID_BOM, VALID_CPL, artifact_record, release_fixture, run_cli,
)


class FrozenAssemblySidesTest(unittest.TestCase):
    def test_direct_validation_uses_frozen_cpl_faces(self):
        top = VALID_CPL
        bottom = top.replace(b",Top,", b",Bottom,")
        both = top + b"R3,1,2,Back,0\n"
        cases = (
            (["Top"], bottom, "CPL side counts {\"bottom\": 1}"),
            (["Bottom"], bottom, None),
            (["Top"], top, None),
            (" bottom + tOP ", both, None),
            (["Top", "Bottom"], top, "assembly_sides mismatch"),
            (["Top"], both, "assembly_sides mismatch"),
            ([], both, "assembly_sides must contain Top and/or Bottom"),
            (["Top"], top.splitlines(keepends=True)[0], "bom_missing_from_cpl"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (declared, cpl, error) in enumerate(cases):
                with self.subTest(declared=declared, cpl=cpl):
                    root = Path(directory) / str(index)
                    data = release_fixture(root, cpl=cpl)
                    self.assertNotIn("assembly_check", data["verification"])
                    if cpl == both:
                        data["artifacts"]["bom"] = artifact_record(root, "bom", VALID_BOM + b"R3,false\n")
                    data["constraints"]["assembly_sides"] = declared
                    manifest = root / "manifest.json"
                    manifest.write_text(json.dumps(data), encoding="utf-8")
                    for flags in ((), ("--confine-to-manifest-dir",)):
                        checked = run_cli(RELEASE_SCRIPTS / "validate_release_manifest.py", manifest, *flags)
                        self.assertEqual(checked.returncode, int(error is not None), checked.stdout + checked.stderr)
                        errors = json.loads(checked.stdout)["errors"]
                        if error:
                            self.assertIn(error, " ".join(errors))
                        else:
                            self.assertEqual(errors, [])

    def test_builder_and_program_consumer_block_side_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = release_fixture(root, cpl=VALID_CPL.replace(b",Top,", b",Bottom,"))
            manifest = root / "manifest.json"
            args = ["--output", manifest, "--release", "fixture", "--revision", "A", "--status", "PASS"]
            for role, artifact in data["artifacts"].items():
                args.extend(("--artifact", f"{role}={root / artifact['path']}", "--artifact-revision", f"{role}=A"))
            for name, value in data["verification"].items():
                args.extend(("--verification", f"{name}={value}"))
            for name, value in data["constraints"].items():
                if name != "assembly_sides":
                    args.extend(("--constraint", f"{name}={value}"))
            builder = RELEASE_SCRIPTS / "build_release_manifest.py"
            rejected = run_cli(builder, *args, "--constraint", "assembly_sides=Top")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("assembly_sides mismatch", rejected.stderr)
            self.assertFalse(manifest.exists())
            accepted = run_cli(builder, *args, "--constraint", "assembly_sides=Bottom")
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            built = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(built["verification"]["assembly_check"]["status"], "matched")
            validate = run_cli(RELEASE_SCRIPTS / "validate_release_manifest.py", manifest,
                               "--confine-to-manifest-dir", "--formal")
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

            # The assembly_check record and all artifact hashes still match after only a declaration is edited.
            built["constraints"]["assembly_sides"] = "Top"
            manifest.write_text(json.dumps(built), encoding="utf-8")
            program = runpy.run_path(str(PROGRAM_STATE))
            with patch.object(sys, "path", sys.path.copy()):
                with self.assertRaisesRegex(ValueError, "assembly_sides mismatch"):
                    program["verified_release"](manifest, root)


IDN = "RIGOL TECHNOLOGIES,DS1054Z,FIXTURE,00.04.04.SP4"
FRAME = b"#9000000003\x7f\x80\x82\n"
PREAMBLE = "0,0,3,1,0.25,-0.5,0,0.5,3,127"
SCREEN_SETTINGS = {"idn": IDN, "source": "CHAN1", "mode": "NORM", "data_format": "BYTE",
                   "start": 1, "stop": 3, "timebase": "MAIN", "amplitude_unit": "VOLT"}
DECODER = SKILLS / "visa-debug/scripts/waveform_readback.py"


class ScreenWaveformTest(unittest.TestCase):
    def setUp(self):
        self.decode = runpy.run_path(str(DECODER))["decode_screen_waveform"]

    def test_rigol_byte_offsets_are_codes_and_signed_time_has_seconds(self):
        result = self.decode(FRAME, PREAMBLE, **SCREEN_SETTINGS)
        self.assertEqual(result.times_s, [-0.5, -0.25, 0.0])
        self.assertEqual(result.values_v, [-1.5, -1.0, 0.0])

    def test_ascii_voltages_are_already_scaled(self):
        result = self.decode(b"-1.5,-1,0\r\n", "2" + PREAMBLE[1:], **{**SCREEN_SETTINGS, "data_format": "ASC"})
        self.assertEqual(result.values_v, [-1.5, -1.0, 0.0])
        self.assertEqual(result.times_s, [-0.5, -0.25, 0.0])

    def test_incomplete_or_contradictory_capture_cannot_be_converted(self):
        cases = (
            (FRAME, "", {}),
            (FRAME, PREAMBLE.replace("0.25", "0"), {}),
            (FRAME, PREAMBLE.replace(",0.5,3", ",nan,3"), {}),
            (FRAME, PREAMBLE.replace(",0.5,3", ",0,3"), {}),
            (FRAME, PREAMBLE, {"amplitude_unit": "UNKN"}),
            (FRAME, PREAMBLE, {"timebase": "XY"}),
            (FRAME, PREAMBLE, {"idn": "OTHER,DS1054Z,FIXTURE,1"}),
            (FRAME, PREAMBLE, {"source": "MATH"}),
            (FRAME, PREAMBLE, {"start": 2}),
            (FRAME, PREAMBLE, {"data_format": "ASC"}),
            (FRAME[:-3], PREAMBLE, {}),
            (FRAME.replace(b"000000003", b"000000002"), PREAMBLE, {}),
            (b"127,0,inf", "2" + PREAMBLE[1:], {"data_format": "ASC"}),
        )
        for frame, preamble, settings in cases:
            with self.subTest(frame=frame, preamble=preamble, settings=settings):
                with self.assertRaises(ValueError):
                    self.decode(frame, preamble, **{**SCREEN_SETTINGS, **settings})


class RigolStub:
    def __init__(self, *, preamble=PREAMBLE, recovery_failure=False):
        self.trace = []
        self.settings = {":WAV:SOUR": "CHAN2", ":WAV:MODE": "RAW", ":WAV:FORM": "WORD",
                         ":WAV:STAR": "20", ":WAV:STOP": "2000"}
        self.original_settings = self.settings.copy()
        self.preamble = preamble
        self.recovery_failure = recovery_failure

    def write(self, command):
        self.trace.append(command)
        if command == ":WAV:DATA?":
            return
        key, value = command.split(" ", 1)
        if command == ":WAV:MODE NORM":
            self.settings.update({":WAV:STAR": "1", ":WAV:STOP": "3"})
        if self.recovery_failure and command == ":WAV:SOUR CHAN2":
            raise OSError("synthetic failed source restore")
        self.settings[key] = value

    def query(self, command):
        self.trace.append(command)
        if command == ":WAV:PRE?" and self.preamble is None:
            raise OSError("synthetic preamble timeout")
        responses = {"*IDN?": IDN, ":WAV:PRE?": self.preamble, ":TIM:MODE?": "MAIN",
                     ":CHAN1:UNIT?": "VOLT", ":CHAN1:PROB?": "1", ":CHAN1:RANG?": "100"}
        return responses[command] if command in responses else self.settings[command.rstrip("?")]

    def read_raw(self):
        self.trace.append("read_raw")
        return FRAME


@unittest.skipUnless(os.environ.get("VISA_LOCAL_SCRIPT"), "no local VISA CLI selected for stub verification")
class LocalVisaCaptureTest(unittest.TestCase):
    def setUp(self):
        script = Path(os.environ["VISA_LOCAL_SCRIPT"])
        with patch.object(sys, "path", [str(script.parent), *sys.path]):
            self.capture = runpy.run_path(str(script))["capture_waveform"]

    def test_failed_preamble_preserves_raw_and_restores_transfer_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "wave.csv"
            instrument = RigolStub(preamble=None)
            report = self.capture(instrument, "stub", str(out), "byte", "CHAN1")
            self.assertEqual(report.status, "uncalibrated")
            self.assertEqual(report.values, [])
            self.assertIsNone(report.output_file)
            self.assertFalse(out.exists())
            self.assertEqual(Path(report.raw_file).read_bytes(), FRAME)
            metadata = json.loads(Path(report.metadata_file).read_text(encoding="utf-8"))
            self.assertEqual(metadata["raw_sha256"], hashlib.sha256(FRAME).hexdigest())
            self.assertEqual(metadata["capture_after"]["errors"], [":WAV:PRE?: synthetic preamble timeout"])
            self.assertEqual(metadata["recovery"]["status"], "restored")
            self.assertEqual(instrument.settings, instrument.original_settings)

    def test_valid_capture_writes_si_columns_and_restore_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "valid.csv"
            instrument = RigolStub()
            report = self.capture(instrument, "stub", str(out), "byte", "CHAN1")
            self.assertEqual(report.status, "success", report.evidence)
            with out.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(list(csv.reader(handle)), [["time_s", "voltage_v"], ["-0.5", "-1.5"],
                                                           ["-0.25", "-1.0"], ["0.0", "0.0"]])
            self.assertEqual(instrument.settings, instrument.original_settings)

            failed_out = Path(directory) / "failed.csv"
            failure = self.capture(RigolStub(recovery_failure=True), "stub", str(failed_out), "byte", "CHAN1")
            self.assertEqual(failure.failure_category, "restore-unverified")
            self.assertEqual(failure.status, "failure")
            self.assertFalse(failed_out.exists())
            self.assertEqual(Path(failure.raw_file).read_bytes(), FRAME)

    def test_scale_changed_during_read_cannot_produce_engineering_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            instrument = RigolStub()
            read_raw = instrument.read_raw

            def read_while_scale_changes():
                frame = read_raw()
                instrument.preamble = PREAMBLE.replace(",0.5,3", ",0.25,3")
                return frame

            instrument.read_raw = read_while_scale_changes
            out = Path(directory) / "wave.csv"
            report = self.capture(instrument, "stub", str(out), "byte", "CHAN1")
            self.assertEqual(report.status, "uncalibrated")
            self.assertFalse(out.exists())
            self.assertEqual(Path(report.raw_file).read_bytes(), FRAME)
            self.assertEqual(instrument.settings, instrument.original_settings)

    def test_unsupported_identity_and_unverified_baseline_stop_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            for target in ("*IDN?", ":WAV:STAR?"):
                instrument = RigolStub()
                query = instrument.query

                def conflicting_readback(command):
                    return "?" if command == target else query(command)

                instrument.query = conflicting_readback
                with self.subTest(query=target):
                    report = self.capture(instrument, "stub", str(Path(directory) / "wave.csv"), "byte", "CHAN1")
                    self.assertEqual(report.status, "failure")
                    self.assertIsNone(report.raw_file)
                    self.assertTrue(all(command.endswith("?") for command in instrument.trace))
