"""本机计算 ADC 一阶建立误差，或对照 PI/PDN 目标阻抗预算。"""

import argparse
import engineering_models
import csv
from decimal import Decimal, DecimalException
from fractions import Fraction
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import sys


def finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError("输入须为有限数值")
    return number


def number(value):
    try:
        result = Decimal(value)
    except DecimalException:
        raise argparse.ArgumentTypeError("输入须为有限十进制数") from None
    if not result.is_finite():
        raise argparse.ArgumentTypeError("输入须为有限十进制数")
    return result


def adc(args):
    if args.step_v < 0 or min(args.acquisition_s, args.error_budget_v, args.resistance_ohm, args.capacitance_f) <= 0:
        raise ValueError("阶跃幅值须非负，采集窗、误差预算、R 和 C 须大于零")
    tau = args.resistance_ohm * args.capacitance_f
    if not math.isfinite(tau) or tau == 0:
        raise ValueError("RC 时间常数超出可计算的范围")
    if args.step_v > args.error_budget_v:
        needed = math.log(args.step_v) - math.log(args.error_budget_v)
        # log1p preserves a nonzero gap when two nearby logarithms round to the same float.
        if needed == 0:
            needed = math.log1p((args.step_v - args.error_budget_v) / args.error_budget_v)
        within = args.acquisition_s / tau >= needed
        limit = args.acquisition_s / needed
        if not math.isfinite(limit) or limit == 0:
            raise ValueError("时间常数上限超出可计算的范围")
    else:
        within = True
        limit = None
    decay = args.acquisition_s / tau
    residual = math.exp(math.log(args.step_v) - decay) if args.step_v else 0.0
    return {
        "kind": "adc-settling", "scope": "one_pole_linear_step",
        "status": "within_model_budget" if within else "exceeds_model_budget",
        "inputs": {
            "step_v": args.step_v, "acquisition_s": args.acquisition_s,
            "error_budget_v": args.error_budget_v, "resistance_ohm": args.resistance_ohm,
            "capacitance_f": args.capacitance_f,
        },
        "tau_s": tau, "tau_limit_s": limit, "residual_v": residual,
    }


def sweep(path, low, high, delta_v, delta_i):
    raw = path.read_bytes()
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != ["frequency_hz", "impedance_ohm"]:
        raise ValueError("扫频 CSV 表头应为 frequency_hz,impedance_ohm")
    points = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"扫频 CSV 第 {reader.line_num} 行列数有误")
        frequency = number(row["frequency_hz"])
        impedance = number(row["impedance_ohm"])
        if frequency < 0 or impedance < 0 or frequency in points:
            raise ValueError(f"扫频 CSV 第 {reader.line_num} 行频率重复或数值为负")
        points[frequency] = impedance
    if not points:
        raise ValueError("扫频 CSV 缺少采样点")
    selected = {freq: z for freq, z in points.items() if low <= freq <= high}
    exact_target = Fraction(delta_v) / Fraction(delta_i)
    exceeded = [freq for freq, z in selected.items() if Fraction(z) > exact_target]
    missing_bounds = [str(bound) for bound in (low, high) if bound not in selected]
    if exceeded:
        status = "sample_limit_exceeded"
    elif missing_bounds:
        status = "sample_coverage_incomplete"
    else:
        status = "within_sampled_points"
    peak = max(selected, key=lambda freq: (selected[freq], -freq)) if selected else None
    return {
        "status": status, "sweep_sha256": sha256(raw).hexdigest(), "points_in_band": len(selected),
        "missing_endpoint_samples_hz": missing_bounds,
        "over_limit_count": len(exceeded), "first_over_limit_hz": [str(f) for f in sorted(exceeded)[:10]],
        "peak": {"frequency_hz": str(peak), "impedance_ohm": str(selected[peak])} if peak is not None else None,
    }


def pdn(args):
    if args.delta_v <= 0 or args.delta_i_a <= 0 or not 0 <= args.fmin_hz < args.fmax_hz:
        raise ValueError("压降预算、阶跃电流须大于零，且 0 ≤ 最低频率 < 最高频率")
    target = args.delta_v / args.delta_i_a
    if not target.is_finite() or target == 0:
        raise ValueError("目标阻抗超出可计算的范围")
    result = {
        "kind": "pdn-target", "scope": "flat_target_sample_screen",
        "status": "target_defined", "target_ohm": str(target),
        "inputs": {
            "delta_v": str(args.delta_v), "delta_i_a": str(args.delta_i_a),
            "fmin_hz": str(args.fmin_hz), "fmax_hz": str(args.fmax_hz),
        },
    }
    if args.sweep:
        result.update(sweep(args.sweep, args.fmin_hz, args.fmax_hz, args.delta_v, args.delta_i_a))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    rc = commands.add_parser("adc-settling", allow_abbrev=False)
    for name in ("step-v", "acquisition-s", "error-budget-v", "resistance-ohm", "capacitance-f"):
        rc.add_argument("--" + name, required=True, type=finite)
    pdn_parser = commands.add_parser("pdn-target", allow_abbrev=False)
    for name in ("delta-v", "delta-i-a", "fmin-hz", "fmax-hz"):
        pdn_parser.add_argument("--" + name, required=True, type=number)
    pdn_parser.add_argument("--sweep", type=Path, help="已有的频率和阻抗幅值 CSV")
    for command in (rc, pdn_parser):
        command.add_argument("--context", type=Path, help="optional model and input-bounds declaration")
    engineering_models.add_command(commands)
    args = parser.parse_args()
    try:
        if args.command == "evaluate":
            result = engineering_models.from_cli(args)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False, default=engineering_models.json_number))
            return {"pass": 0, "fail": 1, "indeterminate": 2}[result["status"]]
        result = adc(args) if args.command == "adc-settling" else pdn(args)
        verdict = {
            "sample_coverage_incomplete": "indeterminate", "sample_limit_exceeded": "fail",
            "exceeds_model_budget": "fail",
        }.get(result["status"], "pass")
        code = engineering_models.contextual_result(result, verdict, result["scope"], args.context)
    except (OSError, ValueError, TypeError, KeyError, argparse.ArgumentTypeError, csv.Error, DecimalException, OverflowError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
