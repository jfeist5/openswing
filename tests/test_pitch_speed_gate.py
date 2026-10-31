"""Pitch mode picks speeds per radar report, gated by the strongest echo.

Bench captures on an OPS243-A (hand moves 2-3 ft from the radar) showed that
taking the fastest inbound candidate lets faint ghosts through: away moves
registered as pitches and readings reached 45-50 mph. The fixture holds real
both-direction reports from that capture.
"""

import json
from pathlib import Path

import pytest

from openflight.ops243 import Direction, SpeedReading
from openflight.swing_speed import (
    PITCH_DOMINANT_FRACTION,
    PITCH_MIN_MAGNITUDE,
    PitchSpeedMonitor,
)

FIXTURE = Path(__file__).parent / "fixtures" / "pitch_bench_capture.jsonl"


def _reading(speed, direction, magnitude):
    return SpeedReading(speed=speed, direction=direction, magnitude=magnitude)


def _inbound(speed, magnitude):
    return _reading(speed, Direction.INBOUND, magnitude)


def _outbound(speed, magnitude):
    return _reading(speed, Direction.OUTBOUND, magnitude)


def _monitor(**kwargs):
    return PitchSpeedMonitor(
        trigger_threshold_mph=kwargs.pop("trigger_threshold_mph", 15.0), **kwargs
    )


def _select(monitor, report):
    return monitor._select_report_reading(report)  # pylint: disable=protected-access


def test_gate_defaults():
    monitor = PitchSpeedMonitor()

    assert PITCH_MIN_MAGNITUDE == 50.0
    assert PITCH_DOMINANT_FRACTION == 0.10
    assert monitor.min_magnitude == 50.0


def test_min_magnitude_can_be_overridden_and_must_not_be_negative():
    assert PitchSpeedMonitor(min_magnitude=0.0).min_magnitude == 0.0
    with pytest.raises(ValueError, match="min_magnitude"):
        PitchSpeedMonitor(min_magnitude=-1.0)


def test_report_dominated_by_outbound_echo_yields_nothing():
    """An away move: strong outbound hand echo plus a ~3x inbound ghost."""
    report = [_outbound(14.7, 2071.0), _inbound(44.8, 239.0), _inbound(17.1, 300.0)]

    assert _select(_monitor(), report) is None


def test_faint_fast_candidate_is_ignored_next_to_a_strong_inbound_echo():
    """A toward punch: strong hand echo at 16 mph plus a faint 45.7 mph stray peak."""
    report = [_inbound(16.3, 2133.0), _inbound(45.7, 21.0), _outbound(29.4, 252.0)]

    selected = _select(_monitor(), report)

    assert selected is not None
    assert selected.speed == 16.3


def test_fastest_candidate_at_or_above_the_fraction_wins():
    """A faint but real fast echo (e.g. the ball next to the pitcher's body) survives."""
    report = [_inbound(20.0, 600.0), _inbound(55.0, 60.0), _inbound(62.0, 59.9)]

    selected = _select(_monitor(), report)

    assert selected.speed == 55.0


def test_noise_level_report_yields_nothing():
    """A still room: the strongest echo is at the ~20-28 noise floor."""
    report = [_inbound(16.3, 26.0), _outbound(10.6, 22.0)]

    assert _select(_monitor(), report) is None


def test_noise_floor_is_inclusive_and_configurable():
    report = [_inbound(18.0, 50.0)]

    assert _select(_monitor(), report).speed == 18.0
    assert _select(_monitor(min_magnitude=0.0), [_inbound(18.0, 26.0)]).speed == 18.0


def test_selected_candidate_must_still_fit_the_speed_window():
    monitor = _monitor(trigger_threshold_mph=30.0, max_speed_mph=80.0)

    assert _select(monitor, [_inbound(20.0, 900.0)]) is None
    assert _select(monitor, [_inbound(95.0, 900.0)]) is None
    assert _select(monitor, [_inbound(65.0, 900.0), _inbound(95.0, 800.0)]).speed == 65.0


def test_reports_without_magnitudes_yield_nothing():
    """Without OM magnitudes the gate cannot tell echoes from ghosts."""
    assert _select(_monitor(), [_inbound(40.0, None), _inbound(41.0, None)]) is None
    assert _select(_monitor(), []) is None


class _FakeClock:
    """Stops the loop after a simulated time budget so a broken fake fails fast."""

    def __init__(self, budget_s=120.0):
        self.start = self.now = 1000.0
        self.budget_s = budget_s
        self.monitor = None
        self.timed_out = False

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.now - self.start > self.budget_s and self.monitor is not None:
            self.timed_out = True
            self.monitor._running = False  # pylint: disable=protected-access


class _ReportRadar:
    """Plays one recorded report per poll, then goes quiet and stops the loop."""

    def __init__(self, clock, reports, quiet_polls=1500):
        self.clock = clock
        self.reports = list(reports)
        self.quiet_polls = quiet_polls
        self.monitor = None

    def read_speed_reports_nonblocking(self):
        if self.reports:
            report = self.reports.pop(0)
            for reading in report:
                reading.timestamp = self.clock.now
            return [report]
        self.quiet_polls -= 1
        if self.quiet_polls <= 0:
            self.monitor._running = False  # pylint: disable=protected-access
        return []


def _recorded_moves():
    moves = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        window = json.loads(line)
        reports = [
            [
                _reading(speed, Direction(direction), magnitude)
                for speed, direction, magnitude in report
            ]
            for report in window["reports"]
        ]
        moves.append((window["move"], window["rep"], reports))
    return moves


def _replay(monkeypatch, reports):
    clock = _FakeClock()
    monkeypatch.setattr("openflight.swing_speed.time", clock)
    monitor = _monitor()
    clock.monitor = monitor
    radar = _ReportRadar(clock, reports)
    radar.monitor = monitor
    monitor.radar = radar
    events = []
    monitor._event_callback = events.append  # pylint: disable=protected-access
    monitor._running = True  # pylint: disable=protected-access
    monitor._capture_loop()  # pylint: disable=protected-access
    assert not clock.timed_out, "capture loop never went quiet; check the fake radar"
    return events


RECORDED = _recorded_moves()


def test_fixture_holds_the_expected_recorded_moves():
    assert [(move, rep) for move, rep, _ in RECORDED] == [
        ("TOWARD", 1),
        ("TOWARD", 2),
        ("TOWARD", 3),
        ("TOWARD", 4),
        ("TOWARD", 5),
        ("AWAY", 3),
        ("AWAY", 4),
        ("AWAY", 5),
    ]


@pytest.mark.parametrize(
    ("rep", "expected_peak"),
    [(1, 20.38), (2, 17.12), (3, 19.57), (4, 21.2), (5, 16.31)],
)
def test_recorded_toward_punch_registers_one_pitch_at_hand_speed(monkeypatch, rep, expected_peak):
    reports = next(r for move, n, r in RECORDED if move == "TOWARD" and n == rep)

    events = _replay(monkeypatch, reports)

    assert len(events) == 1
    assert events[0].peak_speed_mph == expected_peak
    assert events[0].mode == "pitch-speed"


@pytest.mark.parametrize("rep", [3, 4, 5])
def test_recorded_away_move_does_not_register_a_pitch(monkeypatch, rep):
    reports = next(r for move, n, r in RECORDED if move == "AWAY" and n == rep)

    assert _replay(monkeypatch, reports) == []
