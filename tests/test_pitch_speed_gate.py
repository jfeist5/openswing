"""Pitch mode picks speeds per radar report, gated by the strongest echo.

Bench captures on an OPS243-A showed two problems with taking the fastest
inbound candidate: faint ghosts let away moves register (fixed by gating each
report on its strongest echo), and readings came from the top edge of an echo,
not its peak (toss echoes read ~2.5 mph high, a 40.8 mph throw read 44.0).
One moving object fills several neighboring speed steps, so candidates are
grouped into echoes and each echo is read at its strongest step. The fixtures
hold real both-direction reports from those captures.
"""

import json
from pathlib import Path

import pytest

from openflight.ops243 import Direction, SpeedReading
from openflight.swing_speed import (
    PITCH_DOMINANT_FRACTION,
    PITCH_ECHO_GAP_MPH,
    PITCH_MIN_ECHO_STEPS,
    PITCH_MIN_MAGNITUDE,
    PitchSpeedMonitor,
)

FIXTURES = Path(__file__).parent / "fixtures"
BENCH_FIXTURE = FIXTURES / "pitch_bench_capture.jsonl"
TOSS_FIXTURE = FIXTURES / "pitch_toss_capture.jsonl"

# One speed step of the 512-point pitch FFT at 30 ksps.
STEP_MPH = 0.82


def _reading(speed, direction, magnitude):
    return SpeedReading(speed=speed, direction=direction, magnitude=magnitude)


def _inbound(speed, magnitude):
    return _reading(speed, Direction.INBOUND, magnitude)


def _outbound(speed, magnitude):
    return _reading(speed, Direction.OUTBOUND, magnitude)


def _echo(speed, magnitude, steps=2, direction=Direction.INBOUND):
    """A moving object's echo: its strongest step plus weaker faster neighbor steps."""
    return [
        _reading(round(speed + i * STEP_MPH, 2), direction, magnitude * 0.8**i)
        for i in range(steps)
    ]


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
    assert PITCH_ECHO_GAP_MPH == 1.2
    assert PITCH_MIN_ECHO_STEPS == 2
    assert monitor.min_magnitude == 50.0


def test_min_magnitude_can_be_overridden_and_must_not_be_negative():
    assert PitchSpeedMonitor(min_magnitude=0.0).min_magnitude == 0.0
    with pytest.raises(ValueError, match="min_magnitude"):
        PitchSpeedMonitor(min_magnitude=-1.0)


def test_report_dominated_by_outbound_echo_yields_nothing():
    """An away move: strong outbound hand echo plus a ~3x inbound ghost."""
    report = [
        *_echo(14.7, 2071.0, direction=Direction.OUTBOUND),
        *_echo(44.8, 239.0),
        *_echo(17.1, 300.0),
    ]

    assert _select(_monitor(), report) is None


def test_faint_fast_stray_is_ignored_next_to_a_strong_inbound_echo():
    """A toward punch: strong hand echo at 16 mph plus a faint 45.7 mph stray peak."""
    report = [*_echo(16.3, 2133.0), *_echo(45.7, 21.0), _outbound(29.4, 252.0)]

    selected = _select(_monitor(), report)

    assert selected is not None
    assert selected.speed == 16.3


def test_fastest_echo_at_or_above_the_fraction_wins():
    """A faint but real fast echo (the ball next to the pitcher's body) survives."""
    report = [*_echo(20.0, 600.0), *_echo(55.0, 60.0), *_echo(62.0, 59.9)]

    selected = _select(_monitor(), report)

    assert selected.speed == 55.0


def test_echo_is_read_at_its_strongest_step_not_its_top_edge():
    """The 44 mph throw: the echo peaked at 40.8 mph; its faint top edge was 44.0."""
    report = [
        _inbound(40.0, 53.0),
        _inbound(40.8, 57.0),
        _inbound(41.6, 56.0),
        _inbound(42.4, 51.0),
        _inbound(43.2, 44.0),
        _inbound(44.0, 34.0),
    ]

    assert _select(_monitor(), report).speed == 40.8


def test_neighbor_steps_join_one_echo_and_a_two_step_gap_splits_it():
    report = [
        _inbound(20.0, 300.0),
        _inbound(20.8, 250.0),
        # 1.7 mph above the last step: a separate one-step echo, ignored.
        _inbound(22.5, 280.0),
    ]

    assert _select(_monitor(), report).speed == 20.0


def test_one_step_echo_is_ignored_however_fast():
    """A lone step (the walking strays at 26.1 mph) is not a moving object."""
    report = [*_echo(12.2, 180.0, steps=3), _inbound(26.1, 34.0)]

    assert _select(_monitor(trigger_threshold_mph=12.0), report).speed == 12.2


def test_inbound_and_outbound_steps_never_share_an_echo():
    """An inbound step next to outbound steps at the same speed stays a one-step echo."""
    report = [_inbound(30.0, 400.0), _outbound(30.8, 350.0), _outbound(31.6, 300.0)]

    assert _select(_monitor(), report) is None


def test_noise_level_report_yields_nothing():
    """A still room: the strongest echo is at the ~20-28 noise floor."""
    report = [*_echo(16.3, 26.0), *_echo(10.6, 22.0, direction=Direction.OUTBOUND)]

    assert _select(_monitor(), report) is None


def test_noise_floor_is_inclusive_and_configurable():
    assert _select(_monitor(), _echo(18.0, 50.0)).speed == 18.0
    assert _select(_monitor(), _echo(18.0, 49.9)) is None
    assert _select(_monitor(min_magnitude=0.0), _echo(18.0, 26.0)).speed == 18.0


def test_selected_echo_must_still_fit_the_speed_window():
    monitor = _monitor(trigger_threshold_mph=30.0, max_speed_mph=80.0)

    assert _select(monitor, _echo(20.0, 900.0)) is None
    assert _select(monitor, _echo(95.0, 900.0)) is None
    assert _select(monitor, [*_echo(65.0, 900.0), *_echo(95.0, 800.0)]).speed == 65.0


def test_reports_without_magnitudes_yield_nothing():
    """Without OM magnitudes the gate cannot tell echoes from ghosts."""
    assert _select(_monitor(), [_inbound(40.0, None), _inbound(40.8, None)]) is None
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


def _to_readings(report):
    return [
        _reading(speed, Direction(direction), magnitude) for speed, direction, magnitude in report
    ]


def _bench_moves():
    moves = []
    for line in BENCH_FIXTURE.read_text(encoding="utf-8").splitlines():
        window = json.loads(line)
        moves.append((window["move"], window["rep"], [_to_readings(r) for r in window["reports"]]))
    return moves


def _toss_events():
    events = []
    for line in TOSS_FIXTURE.read_text(encoding="utf-8").splitlines():
        window = json.loads(line)
        reports = [_to_readings(r["candidates"]) for r in window["reports"]]
        events.append((window["label"], window["event"], window["logged_peak_mph"], reports))
    return events


def _replay(monkeypatch, reports, **monitor_kwargs):
    clock = _FakeClock()
    monkeypatch.setattr("openflight.swing_speed.time", clock)
    monitor = _monitor(**monitor_kwargs)
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


BENCH = _bench_moves()
TOSSES = _toss_events()


def test_bench_fixture_holds_the_expected_recorded_moves():
    assert [(move, rep) for move, rep, _ in BENCH] == [
        ("TOWARD", 1),
        ("TOWARD", 2),
        ("TOWARD", 3),
        ("TOWARD", 4),
        ("TOWARD", 5),
        ("AWAY", 3),
        ("AWAY", 4),
        ("AWAY", 5),
    ]


@pytest.mark.parametrize(("rep", "expected_peak"), [(3, 17.94), (4, 20.38)])
def test_recorded_toward_punch_registers_at_its_echo_peak(monkeypatch, rep, expected_peak):
    reports = next(r for move, n, r in BENCH if move == "TOWARD" and n == rep)

    events = _replay(monkeypatch, reports)

    assert len(events) == 1
    assert events[0].peak_speed_mph == expected_peak
    assert events[0].mode == "pitch-speed"


@pytest.mark.parametrize("rep", [1, 2, 5])
def test_recorded_slow_toward_punch_stays_below_the_threshold(monkeypatch, rep):
    """These punches' echoes peaked at 11-16 mph; only their top edge crossed 15 mph."""
    reports = next(r for move, n, r in BENCH if move == "TOWARD" and n == rep)

    assert _replay(monkeypatch, reports) == []


@pytest.mark.parametrize("rep", [3, 4, 5])
def test_recorded_away_move_does_not_register_a_pitch(monkeypatch, rep):
    reports = next(r for move, n, r in BENCH if move == "AWAY" and n == rep)

    assert _replay(monkeypatch, reports) == []


def test_toss_fixture_holds_ten_tosses_two_walks_and_a_throw():
    assert [(label, n) for label, n, _, _ in TOSSES] == [
        *[("toss", n) for n in range(1, 11)],
        ("walk", 11),
        ("walk", 12),
        ("throw", 13),
    ]


@pytest.mark.parametrize(
    ("event", "expected_peak"),
    [
        (1, 17.14),
        (2, 24.48),
        (3, 35.91),
        (4, 19.59),
        (5, 19.59),
        (6, 31.83),
        (7, 31.01),
        (8, 32.64),
        (9, 33.46),
        (10, 33.46),
        (13, 40.77),
    ],
)
def test_recorded_toss_reads_at_its_strongest_echo(monkeypatch, event, expected_peak):
    """Each pitch matches the fastest strongest-echo speed in its reports, not the top edge."""
    _, _, logged_peak, reports = next(t for t in TOSSES if t[1] == event)

    events = _replay(monkeypatch, reports, trigger_threshold_mph=12.0, max_speed_mph=60.0)

    assert len(events) == 1
    assert events[0].peak_speed_mph == expected_peak
    assert events[0].peak_speed_mph < logged_peak


@pytest.mark.parametrize(("event", "expected_peak"), [(11, 20.4), (12, 17.95)])
def test_recorded_walk_no_longer_reads_from_stray_steps(monkeypatch, event, expected_peak):
    """Walking toward the radar logged 26.1 and 23.7 mph from one-step strays."""
    _, _, logged_peak, reports = next(t for t in TOSSES if t[1] == event)

    events = _replay(monkeypatch, reports, trigger_threshold_mph=12.0, max_speed_mph=60.0)

    assert [e.peak_speed_mph for e in events] == [expected_peak]
    assert expected_peak < logged_peak


class _PolledReportRadar:
    def __init__(self, reports):
        self.reports = reports

    def read_speed_reports_nonblocking(self):
        reports, self.reports = self.reports, []
        return reports


class _FakeSessionLogger:
    def __init__(self, fail=False):
        self.reports = []
        self.fail = fail

    def log_pitch_report(self, report):
        if self.fail:
            raise OSError("disk full")
        self.reports.append(report)


def _poll(monkeypatch, monitor, reports, session):
    monkeypatch.setattr("openflight.swing_speed.get_session_logger", lambda: session)
    monitor.radar = _PolledReportRadar(reports)
    return monitor._next_reading()  # pylint: disable=protected-access


def test_diagnostics_are_off_by_default():
    assert PitchSpeedMonitor().diagnostics is False


def test_diagnostics_log_the_report_behind_each_accepted_reading(monkeypatch):
    session = _FakeSessionLogger()
    accepted = [_inbound(30.2, 287.0), _outbound(9.8, 140.0), _inbound(31.0, 20.0)]
    rejected = [*_echo(14.7, 2071.0, direction=Direction.OUTBOUND), *_echo(44.8, 239.0)]

    reading = _poll(monkeypatch, _monitor(diagnostics=True), [rejected, accepted], session)

    assert reading.speed == 30.2
    assert session.reports == [
        {
            "selected": {"speed": 30.2, "dir": "inbound", "mag": 287.0},
            "dominant": {"speed": 30.2, "dir": "inbound", "mag": 287.0},
            "candidates": [
                {"speed": 30.2, "dir": "inbound", "mag": 287.0},
                {"speed": 9.8, "dir": "outbound", "mag": 140.0},
                {"speed": 31.0, "dir": "inbound", "mag": 20.0},
            ],
        }
    ]


def test_diagnostics_off_logs_nothing(monkeypatch):
    session = _FakeSessionLogger()

    reading = _poll(monkeypatch, _monitor(), [_echo(30.2, 287.0)], session)

    assert reading.speed == 30.2
    assert session.reports == []


def test_diagnostics_without_a_session_logger_still_return_the_reading(monkeypatch):
    reading = _poll(monkeypatch, _monitor(diagnostics=True), [_echo(30.2, 287.0)], None)

    assert reading.speed == 30.2


def test_diagnostics_logging_failure_does_not_drop_the_reading(monkeypatch, caplog):
    session = _FakeSessionLogger(fail=True)

    with caplog.at_level("WARNING", logger="openflight.swing_speed"):
        reading = _poll(monkeypatch, _monitor(diagnostics=True), [_echo(30.2, 287.0)], session)

    assert reading.speed == 30.2
    assert "Failed to log pitch report" in caplog.text
