"""Decode a saved RIGOL DS1054Z analog screen waveform without instrument I/O."""

from dataclasses import dataclass
import math


ANALOG_CHANNELS = ("CHAN1", "CHAN2", "CHAN3", "CHAN4")


def is_ds1054z(idn: str) -> bool:
    fields = [field.strip().upper() for field in idn.split(",")]
    return (len(fields) == 4 and all(fields) and fields[1] == "DS1054Z"
            and fields[0] in {"RIGOL", "RIGOL TECHNOLOGIES", "RIGOL TECHNOLOGIES INC."})


@dataclass(frozen=True)
class ScreenWaveform:
    times_s: list[float]
    values_v: list[float]


def block_payload(frame: bytes) -> bytes:
    # The DS1054Z uses a nine-digit TMC byte count for binary waveforms.
    if not frame.startswith(b"#9") or not frame[2:11].isdigit() or len(frame) < 11:
        raise ValueError("invalid DS1054Z waveform block header")
    end = 11 + int(frame[2:11])
    if end > len(frame) or frame[end:] not in (b"", b"\n", b"\r\n"):
        raise ValueError("waveform block length or terminator does not match the response")
    return frame[11:end]


def decode_screen_waveform(frame: bytes, preamble: str, *, idn: str, source: str, mode: str,
                           data_format: str, start: int, stop: int, timebase: str,
                           amplitude_unit: str) -> ScreenWaveform:
    if not is_ds1054z(idn) or source not in ANALOG_CHANNELS or mode != "NORM":
        raise ValueError("unsupported scope identity, source, or waveform mode")
    if timebase != "MAIN" or amplitude_unit != "VOLT":
        raise ValueError("waveform requires MAIN timebase and VOLT channel units")
    if data_format not in ("BYTE", "ASC"):
        raise ValueError("unsupported waveform format")

    fields = preamble.strip().split(",")
    if len(fields) != 10:
        raise ValueError("waveform preamble requires ten fields")
    format_code, mode_code, points, averages = map(int, fields[:4])
    if format_code != {"BYTE": 0, "ASC": 2}[data_format] or mode_code != 0 or averages < 1:
        raise ValueError("waveform preamble format, mode, or average count does not match the capture")
    if not 1 <= points <= 1200 or start != 1 or stop != points:
        raise ValueError("waveform preamble and readback do not describe the complete screen window")
    x_step, x_origin, x_ref, y_step, y_origin, y_ref = map(float, fields[4:])
    if not all(math.isfinite(value) for value in (x_step, x_origin, x_ref, y_step, y_origin, y_ref)):
        raise ValueError("waveform preamble contains a nonfinite scale, origin, or reference")
    if x_step <= 0 or y_step <= 0 or x_ref != 0:
        raise ValueError("invalid DS1054Z screen scaling or time reference")

    if data_format == "BYTE":
        payload = block_payload(frame)
        # Both vertical offsets in this instrument's preamble are in code units.
        values = [(code - y_origin - y_ref) * y_step for code in payload]
    else:
        payload = block_payload(frame) if frame.startswith(b"#") else frame
        # ASCII replies already contain voltage values.
        values = [float(value) for value in payload.decode("ascii").strip().split(",")]
    if len(values) != points or not all(math.isfinite(value) for value in values):
        raise ValueError("waveform value count or sample values do not match the preamble")
    times = [x_origin + index * x_step for index in range(points)]
    if not all(math.isfinite(value) for value in times) or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("waveform time axis is not finite and strictly increasing")
    return ScreenWaveform(times, values)
