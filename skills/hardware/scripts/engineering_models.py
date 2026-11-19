"""Bounded engineering models for engineering_checks.py. No backend or device I/O."""

import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import json
from pathlib import Path


def quantity(value):
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, str)):
        raise ValueError("expected a finite decimal quantity")
    number = Decimal(value)
    if not number.is_finite() or abs(number.adjusted()) > 300:
        raise ValueError("quantity is outside the supported numeric range")
    return Fraction(number)


def required(values, *keys, other=()):
    extras = set(values).difference(keys, other)
    if extras:
        raise ValueError(f"unsupported model inputs: {sorted(extras)}")
    return [quantity(values[key]) for key in keys]


def ordered(low, high):
    if low > high:
        raise ValueError("lower bound exceeds upper bound")


def compare_interval(low, high, minimum, maximum, reachable=False):
    ordered(low, high)
    ordered(minimum, maximum)
    if minimum <= low and high <= maximum:
        return "pass"
    if high < minimum or low > maximum or reachable:
        return "fail"
    return "indeterminate"


def i2c(values, context):
    vdd, vol, current, rise, cap, resistor, tolerance = required(
        values,
        "vdd_max_v",
        "vol_max_v",
        "iol_min_a",
        "rise_max_s",
        "bus_cap_max_f",
        "r_ohm",
        "tolerance",
    )
    if (
        not 0 <= vol < vdd
        or min(current, rise, cap, resistor) <= 0
        or not 0 <= tolerance < 1
    ):
        raise ValueError("invalid pull-up design limits")
    lower = (vdd - vol) / current
    upper = rise / (Fraction(8473, 10000) * cap)
    low, high = resistor * (1 - tolerance), resistor * (1 + tolerance)
    if lower > upper:
        verdict = (
            "fail" if context.get("corners_reachable") is True else "indeterminate"
        )
    else:
        verdict = compare_interval(
            low, high, lower, upper, context.get("corners_reachable") is True
        )
        if verdict == "fail" and context.get("corners_reachable") is not True:
            verdict = "indeterminate"
    return verdict, {"window_ohm": [lower, upper], "selected_ohm": [low, high]}


def divider(values, context):
    v0, v1, t0, t1, b0, b1, lo, hi = required(
        values,
        "vin_min_v",
        "vin_max_v",
        "top_min_ohm",
        "top_max_ohm",
        "bottom_min_ohm",
        "bottom_max_ohm",
        "allowed_min_v",
        "allowed_max_v",
    )
    for a, b in ((v0, v1), (t0, t1), (b0, b1)):
        ordered(a, b)
    if v0 < 0 or min(t0, b0) <= 0:
        raise ValueError(
            "divider requires nonnegative input voltage and positive resistances"
        )
    minimum, maximum = v0 * b0 / (t1 + b0), v1 * b1 / (t0 + b1)
    return compare_interval(
        minimum, maximum, lo, hi, context.get("corners_reachable") is True
    ), {"output_v": [minimum, maximum]}


def copper(values, context):
    length, width, thickness, current, temp, resistivity, alpha, contact, limit = (
        required(
            values,
            "length_mm",
            "width_mm",
            "finished_copper_um",
            "current_a",
            "copper_temp_c",
            "rho20_ohm_m",
            "alpha_per_k",
            "contact_ohm",
            "maximum_drop_v",
        )
    )
    if (
        min(length, width, thickness, resistivity) <= 0
        or min(current, alpha, contact, limit) < 0
    ):
        raise ValueError("invalid copper dimensions, current or loss budget")
    hot_factor = 1 + alpha * (temp - 20)
    if temp <= Fraction(-27315, 100) or hot_factor <= 0:
        raise ValueError("temperature outside the resistivity model")
    copper_ohm = resistivity * length * 10**6 / (width * thickness) * hot_factor
    drop = (copper_ohm + contact) * current
    return ("pass" if drop <= limit else "fail"), {
        "copper_ohm": copper_ohm,
        "total_drop_v": drop,
        "copper_loss_w": current**2 * copper_ohm,
        "contact_loss_w": current**2 * contact,
    }


def guardband(values, context):
    value, u, lo, hi = required(
        values,
        "value",
        "expanded_uncertainty",
        "minimum",
        "maximum",
        other=("unit", "coverage_probability"),
    )
    if u < 0 or not isinstance(values.get("unit"), str) or not values["unit"].strip():
        raise ValueError(
            "expanded uncertainty must be nonnegative and a common unit is required"
        )
    probability = quantity(values["coverage_probability"])
    if not 0 < probability < 1:
        raise ValueError("coverage probability must be strictly between zero and one")
    return compare_interval(value - u, value + u, lo, hi), {
        "interval": [value - u, value + u],
        "unit": values["unit"],
    }


def stencil(values, context):
    length, width, thickness, minimum, aspect_min = required(
        values,
        "length_mm",
        "width_mm",
        "thickness_mm",
        "minimum_area_ratio",
        "minimum_aspect_exclusive",
    )
    if min(length, width, thickness, minimum, aspect_min) <= 0:
        raise ValueError("positive aperture dimensions and process limits required")
    area_ratio = length * width / (2 * thickness * (length + width))
    aspect = min(length, width) / thickness
    return ("pass" if area_ratio >= minimum and aspect > aspect_min else "fail"), {
        "area_ratio": area_ratio,
        "aspect_ratio": aspect,
        "ideal_volume_mm3": length * width * thickness,
    }


def zero_failure(values, context):
    n = values["sample_count"]
    failures = values["failure_count"]
    if type(n) is not int or n < 1 or type(failures) is not int or failures != 0:
        raise ValueError(
            "requires independent trials, positive integer n, and zero observed failures"
        )
    confidence, target = required(
        values,
        "confidence",
        "target_probability",
        other=("sample_count", "failure_count"),
    )
    if not (0 < confidence < 1 and 0 < target < 1):
        raise ValueError(
            "confidence and target probability must be strictly between zero and one"
        )
    with localcontext() as calc:
        calc.prec = 350

        def decimal(q):
            return Decimal(q.numerator) / Decimal(q.denominator)

        alpha = decimal(1 - confidence)
        bound = 1 - (alpha.ln() / n).exp()
        attained = decimal(1 - target) ** n <= alpha
        return ("pass" if attained else "indeterminate"), {
            "upper_probability": float(bound),
            "sample_count": n,
        }


def tolerance_stack(values, context):
    nominal, lo, hi = required(
        values, "nominal", "minimum", "maximum", other=("unit", "signed_contributions")
    )
    if not isinstance(values.get("unit"), str) or not values["unit"].strip():
        raise ValueError("common unit required")
    intervals = values["signed_contributions"]
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("signed contribution intervals required")
    low = high = nominal
    for interval in intervals:
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("each signed contribution requires two bounds")
        a, b = map(quantity, interval)
        ordered(a, b)
        low += a
        high += b
    return compare_interval(
        low, high, lo, hi, context.get("corners_reachable") is True
    ), {"stack_interval": [low, high], "unit": values["unit"]}


def passivity(values, context):
    # For normalized power waves the Hermitian matrix I - S†S must be PSD.
    # Exact rational principal minors handle equality and coupled-port counterexamples.
    (reference,) = required(values, "reference_ohm", other=("samples",))
    if reference <= 0:
        raise ValueError("common real positive reference impedance required")
    samples = values["samples"]
    if not isinstance(samples, list) or not samples:
        raise ValueError("no frequency samples")
    frequencies = set()
    violations = []
    for sample in samples:
        frequency = quantity(sample["hz"])
        if frequency < 0 or frequency in frequencies:
            raise ValueError("duplicate or negative sample frequency")
        frequencies.add(frequency)
        matrix = sample["s"]
        if (
            not isinstance(matrix, list)
            or len(matrix) != 2
            or any(not isinstance(row, list) or len(row) != 2 for row in matrix)
        ):
            raise ValueError(
                "supported matrix is 2 by 2, row=output port, column=input port"
            )
        ports = []
        for row in matrix:
            for pair in row:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("complex entries require [real, imaginary]")
                ports.append(tuple(map(quantity, pair)))
        a, b, c, d = ports

        def norm(z):
            return z[0] ** 2 + z[1] ** 2

        h11, h22 = 1 - norm(a) - norm(c), 1 - norm(b) - norm(d)
        real = a[0] * b[0] + a[1] * b[1] + c[0] * d[0] + c[1] * d[1]
        imag = a[0] * b[1] - a[1] * b[0] + c[0] * d[1] - c[1] * d[0]
        if min(h11, h22, h11 * h22 - real**2 - imag**2) < 0:
            violations.append(frequency)
    return ("fail" if violations else "pass"), {
        "checked_frequency_samples": len(samples),
        "violating_samples_hz": violations,
        "coverage": "sampled_frequencies_only",
    }


MODELS = {
    "i2c-pullup": ("open_drain_lumped_rc", i2c),
    "divider-wcca": ("positive_unloaded_linear_divider", divider),
    "hot-copper": ("uniform_dc_copper_at_known_temperature", copper),
    "measurement-guardband": ("expanded_interval_inclusive_limits", guardband),
    "stencil-ratio": ("rectangular_straight_wall_aperture", stencil),
    "zero-failure": ("iid_same_mission_zero_failures", zero_failure),
    "tolerance-stack": ("linear_signed_interval_stack", tolerance_stack),
    "s-passivity": ("normalized_power_waves_equal_real_z0", passivity),
}


def evaluate(request):
    name = request["check"]
    model, function = MODELS[name]
    context = request.get("context", {})
    if not isinstance(context, dict) or not isinstance(request.get("inputs"), dict):
        raise ValueError("inputs and context must be objects")
    verdict, result = function(request["inputs"], context)
    missing = []
    if context.get("model") != model:
        missing.append("context.model=" + model)
    if context.get("model_applicable", True) is not True:
        missing.append("applicable model")
    if (
        name == "s-passivity"
        and context.get("coverage", "sampled_frequencies_only")
        != "sampled_frequencies_only"
        and verdict == "pass"
    ):
        missing.append("coverage beyond sampled frequencies")
    if context.get("inputs_bounded") is not True:
        missing.append("context.inputs_bounded=true")
    return {
        "check": name,
        "model": model,
        "scope": "specified_model_only",
        "numeric_status": verdict,
        "status": "indeterminate" if missing else verdict,
        "missing_context": missing,
        "physical_validation": False,
        "result": result,
    }


def contextual_result(report, numeric_status, model, context_path):
    """Legacy flags describe an assumed local model; an explicit context must match it."""
    report["model"] = model
    report["numeric_status"] = numeric_status
    report["verification_status"] = numeric_status
    report["physical_validation"] = False
    if context_path is not None:
        context = json.loads(context_path.read_text(encoding="utf-8-sig"))
        if not isinstance(context, dict):
            raise ValueError("context must be an object")
        if (
            context.get("model") != model
            or context.get("inputs_bounded") is not True
            or context.get("model_applicable", True) is not True
        ):
            report["verification_status"] = "indeterminate"
            report["missing_context"] = [
                "matching applicable model and confirmed input bounds"
            ]
        elif (
            model == "flat_target_sample_screen"
            and context.get("coverage", "sampled_frequencies_only")
            != "sampled_frequencies_only"
            and numeric_status == "pass"
        ):
            report["verification_status"] = "indeterminate"
            report["missing_context"] = ["coverage beyond sampled frequencies"]
    return {"pass": 0, "fail": 1, "indeterminate": 2}[report["verification_status"]]


def add_command(commands):
    parser = commands.add_parser(
        "evaluate", allow_abbrev=False, help="evaluate one bounded engineering model"
    )
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--file", type=Path, help="JSON with check, inputs and context")
    choice.add_argument("--check", choices=sorted(MODELS))
    parser.add_argument("--input", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--assume-model", choices=sorted(m for m, _ in MODELS.values()))
    parser.add_argument("--bounded", action="store_true")
    parser.add_argument("--reachable", action="store_true")


def from_cli(args):
    if args.file is not None:
        if args.input or args.assume_model or args.bounded or args.reachable:
            raise ValueError("--file supplies all inputs and context")
        return evaluate(
            json.loads(args.file.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        )
    inputs = {}
    for field in args.input:
        key, sep, value = field.partition("=")
        if not sep or not key or key in inputs:
            raise ValueError("use unique FIELD=VALUE inputs")
        try:
            inputs[key] = json.loads(value, parse_float=Decimal)
        except json.JSONDecodeError:
            inputs[key] = value
    return evaluate(
        {
            "check": args.check,
            "inputs": inputs,
            "context": {
                "model": args.assume_model,
                "inputs_bounded": args.bounded,
                "corners_reachable": args.reachable,
            },
        }
    )


def json_number(value):
    if isinstance(value, Fraction):
        number = float(value)
        if number == 0 and value != 0:
            raise ValueError("result outside representable output range")
        return number
    raise TypeError(type(value).__name__)
