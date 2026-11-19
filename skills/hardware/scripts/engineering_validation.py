"""Evaluate engineering evidence against explicit design and test limits offline."""

import argparse
from engineering_models import contextual_result
from collections import Counter
import csv
from decimal import Decimal, DecimalException
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys


def number(raw):
    try:
        value = Decimal(raw)
    except DecimalException as error:
        raise argparse.ArgumentTypeError("expected a finite decimal number") from error
    if not value.is_finite():
        raise argparse.ArgumentTypeError("expected a finite decimal number")
    return value


def decide(low, high, bound, direction):
    favorable, adverse = (bound - low, bound - high) if direction == "max" else (high - bound, low - bound)
    status = "within_limit" if adverse >= 0 else "outside_limit" if favorable < 0 else "indeterminate"
    return {
        "status": status, "direction": direction, "limit": bound,
        "interval": [low, high], "worst_margin": adverse,
    }


def limit(args):
    if args.uncertainty < 0 or not args.unit.strip():
        raise ValueError("uncertainty must be nonnegative and unit must be specified")
    return {"unit": args.unit, "value": args.value, "uncertainty": args.uncertainty,
            **decide(args.value - args.uncertainty, args.value + args.uncertainty, args.limit, args.direction)}


def coverage(args):
    if not 0 <= args.minimum_percent <= 100:
        raise ValueError("minimum percent must be between 0 and 100")
    raw = args.faults.read_bytes()
    rows = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if next(rows, None) != ["fault_id", "status"]:
        raise ValueError("CSV header must be fault_id,status")
    counts = Counter(detected=0, missed=0, unknown=0)
    seen = set()
    for row in rows:
        if len(row) != 2 or not row[0].strip() or row[1] not in counts:
            raise ValueError(f"invalid fault observation at CSV line {rows.line_num}")
        key = row[0].strip()
        if key in seen:
            raise ValueError(f"duplicate fault identity at CSV line {rows.line_num}")
        seen.add(key)
        counts[row[1]] += 1
    if not seen:
        raise ValueError("fault list must contain at least one target fault")
    total = len(seen)
    detected = 100 * counts["detected"]
    possible = detected + 100 * counts["unknown"]
    target = Fraction(args.minimum_percent) * total
    status = "within_limit" if detected >= target else "outside_limit" if possible < target else "indeterminate"
    return {
        "status": status, "minimum_percent": args.minimum_percent, "fault_count": total, "counts": dict(counts),
        "percent_interval": [Decimal(detected) / total, Decimal(possible) / total],
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
    }


def rs485_stub(args):
    if args.rise_ns <= 0 or not 0 < args.velocity_factor <= 1 or args.length_m < 0:
        raise ValueError("rise time must be positive, velocity factor in (0,1], and length nonnegative")
    limit_m = args.rise_ns * args.velocity_factor * Decimal("0.299792458") / 10
    return {"scope": "ti_slla272d_rs485_stub_screen", "length_m": args.length_m,
            "rise_ns": args.rise_ns, "velocity_factor": args.velocity_factor,
            "maximum_length_m": limit_m,
            "status": "within_limit" if args.length_m <= limit_m else "outside_limit"}


def junction(args):
    for low, high in (args.top_c, args.psi_c_per_w, args.power_w):
        if low > high:
            raise ValueError("each input range must be ordered low to high")
    if min(*args.psi_c_per_w, *args.power_w) < 0:
        raise ValueError("power and applicable thermal characterization coefficient must be nonnegative")
    low = args.top_c[0] + args.psi_c_per_w[0] * args.power_w[0]
    high = args.top_c[1] + args.psi_c_per_w[1] * args.power_w[1]
    return {"scope": "steady_state_psi_jt_estimate", "unit": "degC", "top_c": args.top_c,
            "psi_c_per_w": args.psi_c_per_w, "power_w": args.power_w,
            **decide(low, high, args.limit_c, "max")}


def annular_ring(args):
    if min(args.pad_min_mm, args.hole_max_mm) <= 0 or min(args.offset_max_mm, args.minimum_ring_mm) < 0:
        raise ValueError("diameters must be positive; offset and minimum ring must be nonnegative")
    lower_bound = (args.pad_min_mm - args.hole_max_mm) / 2 - args.offset_max_mm
    return {"scope": "round_pad_geometry_lower_bound", "unit": "mm", "lower_bound_mm": lower_bound,
            "minimum_ring_mm": args.minimum_ring_mm, "pad_min_mm": args.pad_min_mm,
            "hole_max_mm": args.hole_max_mm, "offset_max_mm": args.offset_max_mm,
            "status": "within_limit" if lower_bound >= args.minimum_ring_mm else "lower_bound_below_limit"}


def add_numbers(parser, *names):
    for name in names:
        parser.add_argument("--" + name, required=True, type=number)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(required=True, dest="check")
    scalar = commands.add_parser("limit", allow_abbrev=False, help="compare one bounded value to an inclusive limit")
    scalar.add_argument("--direction", choices=("min", "max"), required=True)
    scalar.add_argument("--unit", required=True)
    add_numbers(scalar, "value", "uncertainty", "limit")
    scalar.set_defaults(evaluate=limit)
    faults = commands.add_parser("coverage", allow_abbrev=False, help="bound a frozen fault universe's detection coverage")
    faults.add_argument("--faults", required=True, type=Path)
    add_numbers(faults, "minimum-percent")
    faults.set_defaults(evaluate=coverage)
    stub = commands.add_parser("rs485-stub", allow_abbrev=False, help="apply the SLLA272D one-way stub screen")
    add_numbers(stub, "rise-ns", "velocity-factor", "length-m")
    stub.set_defaults(evaluate=rs485_stub)
    thermal = commands.add_parser("junction", allow_abbrev=False, help="bound the steady-state top-temperature estimate")
    for name in ("top-c", "psi-c-per-w", "power-w"):
        thermal.add_argument("--" + name, nargs=2, required=True, type=number, metavar=("LOW", "HIGH"))
    add_numbers(thermal, "limit-c")
    thermal.set_defaults(evaluate=junction)
    ring = commands.add_parser("annular-ring", allow_abbrev=False, help="screen a round pad with bounded drill offset")
    add_numbers(ring, "pad-min-mm", "hole-max-mm", "offset-max-mm", "minimum-ring-mm")
    ring.set_defaults(evaluate=annular_ring)
    for command in (scalar, faults, stub, thermal, ring):
        command.add_argument("--context", type=Path, help="optional model and input-bounds declaration")
    args = parser.parse_args()
    try:
        report = args.evaluate(args)
        verdict = {"within_limit": "pass", "outside_limit": "fail"}.get(report["status"], "indeterminate")
        code = contextual_result(report, verdict, report.get("scope", args.check), args.context)
    except (OSError, ValueError, DecimalException, csv.Error) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps({"check": args.check, **report}, default=str, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
