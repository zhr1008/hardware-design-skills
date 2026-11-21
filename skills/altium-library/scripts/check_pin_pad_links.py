"""Check saved Altium libraries with a single current footprint and same-number pins and pads."""

import argparse
from collections import Counter
from pathlib import Path
import zlib


def check_numbers(pins, pads, problems):
    pin_numbers = Counter(pin.designator for pin in pins)
    pad_numbers = Counter(pad.designator for pad in pads if pad.designator)
    if not pin_numbers or "" in pin_numbers or None in pin_numbers:
        problems.append("missing pin designator or empty pin list")
    for label, numbers in (("pin", pin_numbers), ("pad", pad_numbers)):
        repeated = [name for name, count in numbers.items() if count > 1]
        if repeated:
            problems.append(f"repeated {label} designators: {repeated}")
    missing = sorted(pin_numbers.keys() - pad_numbers.keys(), key=str)
    extra = sorted(pad_numbers.keys() - pin_numbers.keys(), key=str)
    if missing or extra:
        problems.append(f"pin/pad mismatch: missing pads {missing}, extra pads {extra}")


def check_step(pcb_lib, footprint, models, step_dir, problems):
    step_count = 0
    for body in footprint.component_bodies:
        if not body.model_is_embedded or not body.model_id:
            continue
        model = models.get(body.model_id.casefold())
        if not model or not model.is_embedded or not model.payload_available:
            problems.append(f"missing embedded model payload: {body.model_id}")
            continue
        if model.model_format != "step":
            continue
        step_count += 1
        try:
            payload = pcb_lib.get_embedded_model_payload(model.index)
            if not (payload.lstrip().startswith(b"ISO-10303-21;")
                    and payload.rstrip().endswith(b"END-ISO-10303-21;")):
                problems.append(f"invalid STEP framing: {model.name}")
            if step_dir is not None:
                path = step_dir / Path(model.name).name
                if not path.is_file():
                    problems.append(f"missing standalone STEP: {path.name}")
                elif payload != path.read_bytes():
                    problems.append(f"embedded bytes differ from standalone STEP: {path.name}")
        except (ValueError, OSError, RuntimeError, zlib.error) as error:
            problems.append(f"unreadable STEP {model.name}: {error}")
    if not step_count:
        problems.append("no embedded STEP on linked footprint")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schlib", type=Path)
    parser.add_argument("pcblib", type=Path)
    parser.add_argument("--symbol", action="append", help="Check only this symbol (repeatable).")
    parser.add_argument("--require-step", action="store_true", help="Require an embedded STEP for each linked footprint.")
    parser.add_argument("--step-dir", type=Path, help="Require STEP and compare with standalone files in this directory.")
    args = parser.parse_args()

    try:
        from altium_monkey import AltiumPcbLib, AltiumSchLib
        from altium_monkey.altium_record_sch__implementation import AltiumSchMapDefiner
    except ImportError as error:
        parser.error(f"compatible altium-monkey environment required: {error}")

    if args.step_dir is not None and not args.step_dir.is_dir():
        parser.error("--step-dir must name an existing directory")
    try:
        sch = AltiumSchLib(args.schlib)
        pcb = AltiumPcbLib.from_file(args.pcblib)
        verify_step = args.require_step or args.step_dir is not None
        models = {model.id.casefold(): model for model in pcb.embedded_model_summaries()
                  if model.id} if verify_step else {}
    except (ValueError, OSError, RuntimeError, zlib.error) as error:
        parser.error(f"cannot read library evidence: {error}")
    symbols = {symbol.name.casefold(): symbol for symbol in sch.symbols}
    footprints = {footprint.name.casefold(): footprint for footprint in pcb.footprints}
    if len(symbols) != len(sch.symbols) or len(footprints) != len(pcb.footprints):
        parser.error("ambiguous symbol or footprint name")
    selected = dict.fromkeys(name.casefold() for name in args.symbol) if args.symbol else symbols
    if not selected:
        parser.error("no symbols found")

    counts = Counter()
    for name in selected:
        symbol = symbols.get(name)
        if symbol is None:
            print(f"FAIL {name}: symbol not found")
            counts["failed"] += 1
            continue
        problems = []
        links = [link for link in symbol.implementations if link.model_type.upper() == "PCBLIB"]
        if len(links) != 1 or not links[0].is_current:
            problems.append("expected exactly one PCB footprint link, marked current")
        else:
            link = links[0]
            record = {key.upper(): value for key, value in link.serialize_to_record().items()}
            reference = record.get("%UTF8%MODELDATAFILE0") or record.get("MODELDATAFILE0")
            if reference in (None, "", "*") and Path(link.datafile_entity).suffix.casefold() == ".pcblib":
                reference = link.datafile_entity
            if link.datafile_count > 1:
                problems.append("multiple footprint library references require a device-specific check")
            if reference and reference != "*" and (args.schlib.parent / reference).resolve() != args.pcblib.resolve():
                problems.append(f"linked library differs: {reference}")
            footprint = footprints.get(link.model_name.casefold())
            if footprint is None:
                problems.append(f"linked footprint not found: {link.model_name}")
            elif any(isinstance(item, AltiumSchMapDefiner) for item in symbol.objects):
                problems.append("explicit pin mapping requires a device-specific check")
            else:
                check_numbers(symbol.pins, footprint.pads, problems)
                if verify_step:
                    check_step(pcb, footprint, models, args.step_dir, problems)
                if not problems:
                    counts["pins"] += len(symbol.pins)
        if problems:
            print(f"FAIL {symbol.name}: {'; '.join(problems)}")
            counts["failed"] += 1
    print(f"{len(selected) - counts['failed']}/{len(selected)} symbols passed, {counts['pins']} pins verified.")
    return int(bool(counts["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
