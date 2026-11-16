#!/usr/bin/env python3
"""Record every OPS243 speed candidate for later analysis of pitches or hits.

Uses pitch mode's CW radar setup (512-point FFT, both directions by default)
and writes one JSON line per radar report. Type a note and press Enter while
recording (e.g. "stalker 43.5") to save a timestamped marker, such as a
reference radar's reading. Nothing is saved to the radar's flash, and
rolling-buffer mode is always restored on exit.

Run with OpenSwing stopped:
    uv run python scripts/hardware-test/record_speed_reports.py --label hit-tee --seconds 120
"""

import argparse
import json
import queue
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from openflight.ops243 import Direction, OPS243Radar

DIRECTIONS = {"both": None, "inbound": Direction.INBOUND, "outbound": Direction.OUTBOUND}
NUM_REPORTS = 8
POLL_S = 0.002
DEFAULT_OUT_DIR = Path.home() / "openflight_sessions" / "captures"
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _label(value: str) -> str:
    if not _LABEL_PATTERN.match(value):
        raise argparse.ArgumentTypeError("use letters, digits, '-' or '_' only")
    return value


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return seconds


def _min_speed(value: str) -> float:
    speed = float(value)
    if speed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return speed


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--label", type=_label, default="capture", help="Name saved in the file (default: capture)"
    )
    parser.add_argument(
        "--seconds",
        type=_positive_seconds,
        default=None,
        help="Stop after this long (default: Ctrl+C)",
    )
    parser.add_argument(
        "--direction",
        choices=sorted(DIRECTIONS),
        default="both",
        help="Directions the radar reports",
    )
    parser.add_argument(
        "--min-speed",
        type=_min_speed,
        default=10.0,
        help="Radar minimum speed in mph (default: 10)",
    )
    parser.add_argument("--port", default=None, help="OPS243 serial port (default: auto-detect)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output folder (default: {DEFAULT_OUT_DIR})",
    )
    return parser.parse_args(argv)


def read_markers(stream: TextIO, markers: queue.Queue) -> None:
    """Queue each non-blank line typed while recording."""
    for line in stream:
        text = line.strip()
        if text:
            markers.put(text)


def start_marker_thread(markers: queue.Queue) -> None:
    threading.Thread(target=read_markers, args=(sys.stdin, markers), daemon=True).start()


def record(
    radar,
    out: TextIO,
    *,
    seconds: Optional[float],
    markers: queue.Queue,
    clock=time.monotonic,
    sleep=time.sleep,
) -> int:
    """Write every report (and typed marker) until `seconds` elapse; returns the report count."""
    start = clock()
    count = 0
    while seconds is None or clock() - start < seconds:
        t = round(clock() - start, 3)
        while True:
            try:
                text = markers.get_nowait()
            except queue.Empty:
                break
            out.write(json.dumps({"type": "marker", "t": t, "text": text}) + "\n")
        for report in radar.read_speed_reports_nonblocking():
            candidates = [[round(r.speed, 2), r.direction.value, r.magnitude] for r in report]
            out.write(json.dumps({"type": "report", "t": t, "candidates": candidates}) + "\n")
            count += 1
        sleep(POLL_S)
    return count


def main(argv=None) -> Path:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{args.label}.jsonl"

    radar = OPS243Radar(port=args.port)
    radar.connect()
    try:
        radar.configure_for_pitch_speed(min_speed_mph=args.min_speed, num_reports=NUM_REPORTS)
        if DIRECTIONS[args.direction] is not None:
            radar.set_direction_filter(DIRECTIONS[args.direction])
        try:
            firmware = radar.get_firmware_version()
        except Exception:  # pylint: disable=broad-except
            firmware = None
        markers: queue.Queue = queue.Queue()
        start_marker_thread(markers)
        with out_path.open("w", encoding="utf-8") as out:
            header = {
                "type": "header",
                "label": args.label,
                "direction": args.direction,
                "min_speed_mph": args.min_speed,
                "num_reports": NUM_REPORTS,
                "radar_setup": "pitch-speed CW, 512-point FFT",
                "port": radar.port,
                "firmware": firmware,
                "started": datetime.now().isoformat(),
            }
            out.write(json.dumps(header) + "\n")
            print(f"Recording '{args.label}' to {out_path}")
            print("Type a note and press Enter to mark it (e.g. 'stalker 43.5'); Ctrl+C to stop.")
            try:
                count = record(radar, out, seconds=args.seconds, markers=markers)
                print(f"Done: {count} radar reports recorded.")
            except KeyboardInterrupt:
                print("Stopped.")
    finally:
        radar.restore_rolling_buffer_mode()
        radar.disconnect()
    return out_path


if __name__ == "__main__":
    print(f"Saved {main()}")
