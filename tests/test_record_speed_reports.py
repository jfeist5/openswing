"""Tests for the OPS243 speed-report recorder used for facility pitch and hitting captures."""

import io
import json
import queue
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "hardware-test"))

import record_speed_reports as recorder  # noqa: E402

from openflight.ops243 import Direction, SpeedReading  # noqa: E402


def _reading(speed, direction, magnitude):
    return SpeedReading(speed=speed, direction=direction, magnitude=magnitude)


class _FakeClock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _ScriptedRadar:
    """Returns one scripted list of reports per poll, then nothing."""

    def __init__(self, polls):
        self.polls = list(polls)

    def read_speed_reports_nonblocking(self):
        return self.polls.pop(0) if self.polls else []


def _lines(buffer):
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


class TestParseArgs:
    def test_defaults(self):
        args = recorder.parse_args([])

        assert args.label == "capture"
        assert args.seconds is None
        assert args.direction == "both"
        assert args.min_speed == 10.0
        assert args.port is None
        assert args.out_dir == Path.home() / "openflight_sessions" / "captures"

    def test_overrides(self):
        args = recorder.parse_args(
            [
                "--label",
                "hit-tee",
                "--seconds",
                "60",
                "--direction",
                "outbound",
                "--min-speed",
                "20",
            ]
        )

        assert (args.label, args.seconds, args.direction, args.min_speed) == (
            "hit-tee",
            60.0,
            "outbound",
            20.0,
        )

    @pytest.mark.parametrize(
        "argv",
        [
            ["--seconds", "0"],
            ["--seconds", "-5"],
            ["--min-speed", "-1"],
            ["--direction", "sideways"],
            ["--label", "../escape"],
            ["--label", "two words"],
            ["--label", ""],
        ],
    )
    def test_rejects_invalid_arguments(self, argv):
        with pytest.raises(SystemExit) as excinfo:
            recorder.parse_args(argv)

        assert excinfo.value.code == 2


class TestRecord:
    def test_writes_each_report_with_its_time_and_candidates(self):
        clock = _FakeClock()
        radar = _ScriptedRadar(
            [
                [
                    [
                        _reading(40.8, Direction.INBOUND, 57.0),
                        _reading(41.6, Direction.INBOUND, 56.0),
                    ]
                ],
                [],
                [
                    [_reading(12.2, Direction.OUTBOUND, 30.0)],
                    [_reading(39.1, Direction.INBOUND, 113.0)],
                ],
            ]
        )
        out = io.StringIO()

        count = recorder.record(
            radar, out, seconds=1.0, markers=queue.Queue(), clock=clock.monotonic, sleep=clock.sleep
        )

        lines = _lines(out)
        assert count == 3
        assert [line["candidates"] for line in lines] == [
            [[40.8, "inbound", 57.0], [41.6, "inbound", 56.0]],
            [[12.2, "outbound", 30.0]],
            [[39.1, "inbound", 113.0]],
        ]
        assert all(line["type"] == "report" for line in lines)
        assert lines[0]["t"] < lines[1]["t"] <= lines[2]["t"]

    def test_stops_after_the_requested_seconds(self):
        clock = _FakeClock()

        recorder.record(
            _ScriptedRadar([]),
            io.StringIO(),
            seconds=2.5,
            markers=queue.Queue(),
            clock=clock.monotonic,
            sleep=clock.sleep,
        )

        assert 2.5 <= clock.now - 100.0 < 2.6

    def test_writes_markers_typed_during_the_recording(self):
        clock = _FakeClock()
        markers = queue.Queue()
        markers.put("stalker 43.5")
        out = io.StringIO()

        recorder.record(
            _ScriptedRadar([]),
            out,
            seconds=0.1,
            markers=markers,
            clock=clock.monotonic,
            sleep=clock.sleep,
        )

        assert _lines(out) == [{"type": "marker", "t": 0.0, "text": "stalker 43.5"}]


def test_read_markers_skips_blank_lines_and_strips_text():
    markers = queue.Queue()

    recorder.read_markers(io.StringIO("stalker 43.5\n\n  pocket 41  \n"), markers)

    assert [markers.get_nowait(), markers.get_nowait()] == ["stalker 43.5", "pocket 41"]
    assert markers.empty()


class _FakeRadar:
    instances = []

    def __init__(self, port=None):
        self.port = port or "/dev/ttyACM0"
        self.calls = []
        self.fail_on_read = None
        _FakeRadar.instances.append(self)

    def connect(self):
        self.calls.append("connect")

    def get_firmware_version(self):
        return "1.3.0"

    def configure_for_pitch_speed(self, min_speed_mph, num_reports):
        self.calls.append(("configure_for_pitch_speed", min_speed_mph, num_reports))

    def set_direction_filter(self, direction):
        self.calls.append(("set_direction_filter", direction))

    def read_speed_reports_nonblocking(self):
        if self.fail_on_read:
            raise self.fail_on_read
        return []

    def restore_rolling_buffer_mode(self):
        self.calls.append("restore_rolling_buffer_mode")

    def disconnect(self):
        self.calls.append("disconnect")


@pytest.fixture(name="fake_radar")
def _fake_radar(monkeypatch):
    _FakeRadar.instances = []
    monkeypatch.setattr(recorder, "OPS243Radar", _FakeRadar)
    monkeypatch.setattr(recorder, "start_marker_thread", lambda markers: None)
    return _FakeRadar


def test_main_records_with_pitch_setup_and_restores_the_radar(tmp_path, fake_radar):
    out_path = recorder.main(
        [
            "--label",
            "hit-tee",
            "--seconds",
            "0.05",
            "--direction",
            "outbound",
            "--out-dir",
            str(tmp_path),
        ]
    )

    radar = fake_radar.instances[0]
    assert radar.calls == [
        "connect",
        ("configure_for_pitch_speed", 10.0, 8),
        ("set_direction_filter", Direction.OUTBOUND),
        "restore_rolling_buffer_mode",
        "disconnect",
    ]
    header = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
    assert out_path.parent == tmp_path
    assert out_path.name.endswith("_hit-tee.jsonl")
    assert header["type"] == "header"
    assert header["label"] == "hit-tee"
    assert header["direction"] == "outbound"
    assert header["min_speed_mph"] == 10.0
    assert header["port"] == "/dev/ttyACM0"
    assert header["firmware"] == "1.3.0"


def test_main_keeps_both_directions_by_default(tmp_path, fake_radar):
    recorder.main(["--seconds", "0.05", "--out-dir", str(tmp_path)])

    assert not any(
        call[0] == "set_direction_filter"
        for call in fake_radar.instances[0].calls
        if isinstance(call, tuple)
    )


@pytest.mark.parametrize("error", [KeyboardInterrupt(), OSError("serial unplugged")])
def test_main_always_restores_the_radar(tmp_path, fake_radar, monkeypatch, error):
    original_init = _FakeRadar.__init__

    def failing_init(self, port=None):
        original_init(self, port)
        self.fail_on_read = error

    monkeypatch.setattr(_FakeRadar, "__init__", failing_init)

    if isinstance(error, KeyboardInterrupt):
        out_path = recorder.main(["--out-dir", str(tmp_path)])
        assert out_path.exists()
    else:
        with pytest.raises(OSError):
            recorder.main(["--out-dir", str(tmp_path)])

    assert fake_radar.instances[0].calls[-2:] == ["restore_rolling_buffer_mode", "disconnect"]
