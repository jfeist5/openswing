"""Tests for swing speed training mode."""

from datetime import datetime

from openflight.ops243 import Direction, SpeedReading
from openflight.swing_speed import SwingSpeedEvent, SwingSpeedMonitor


def test_build_event_uses_peak_outbound_speed_and_magnitude():
    """A completed swing window should report peak speed and peak magnitude."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=30)
    readings = [
        SpeedReading(
            speed=44.0,
            direction=Direction.OUTBOUND,
            magnitude=12,
            timestamp=100.00,
        ),
        SpeedReading(
            speed=88.4,
            direction=Direction.OUTBOUND,
            magnitude=36,
            timestamp=100.08,
        ),
        SpeedReading(
            speed=73.2,
            direction=Direction.OUTBOUND,
            magnitude=24,
            timestamp=100.13,
        ),
    ]

    event = monitor._build_event(  # pylint: disable=protected-access
        readings=readings,
        trigger_speed=44.0,
        swing_start=100.00,
        swing_end=100.13,
    )

    assert event.peak_speed_mph == 88.4
    assert event.trigger_speed_mph == 44.0
    assert round(event.duration_ms) == 130
    assert event.reading_count == 3
    assert event.peak_magnitude == 36
    assert event.mode == "swing-speed"


def test_session_stats_for_swing_speed_events():
    """Swing speed sessions should summarize rep count, best, average, and last."""
    monitor = SwingSpeedMonitor()
    monitor._events = [  # pylint: disable=protected-access
        SwingSpeedEvent(
            peak_speed_mph=95.0,
            timestamp=datetime.now(),
            duration_ms=320,
            reading_count=5,
            trigger_speed_mph=35.0,
        ),
        SwingSpeedEvent(
            peak_speed_mph=101.4,
            timestamp=datetime.now(),
            duration_ms=340,
            reading_count=7,
            trigger_speed_mph=37.0,
        ),
        SwingSpeedEvent(
            peak_speed_mph=99.2,
            timestamp=datetime.now(),
            duration_ms=300,
            reading_count=6,
            trigger_speed_mph=34.0,
        ),
    ]

    assert monitor.get_session_stats() == {
        "swing_count": 3,
        "best_speed_mph": 101.4,
        "avg_speed_mph": 98.5,
        "last_speed_mph": 99.2,
    }


def test_min_readings_default_rejects_single_spike():
    """The default gate should reject one-off hand-motion or noise spikes."""
    monitor = SwingSpeedMonitor()

    assert monitor.min_readings == 3
    assert monitor.max_speed_mph == 130.0
    assert monitor.single_reading_peak_mph == 60.0
    assert monitor.num_reports == 8
    assert monitor.end_quiet_ms == 1000.0
    assert monitor.rejected_cooldown_ms == 100.0


def test_connect_applies_threshold_to_radar_filter(monkeypatch):
    """Swing mode should not stream low-speed background readings from the OPS."""
    calls = []

    class FakeRadar:
        def __init__(self, port=None):
            self.port = port

        def connect(self):
            calls.append(("connect", None))

        def configure_for_swing_speed_training(self, min_speed_mph=None, num_reports=None):
            calls.append(("configure_for_swing_speed_training", (min_speed_mph, num_reports)))

    monkeypatch.setattr("openflight.swing_speed.OPS243Radar", FakeRadar)

    monitor = SwingSpeedMonitor(port="COM4", trigger_threshold_mph=45.0)

    assert monitor.connect() is True
    # Training owns its own radar setup; it must not route through the launch
    # monitor's configure_for_speed_trigger() (which hands off to the rolling
    # buffer), and the threshold/report count go in as arguments.
    assert calls == [
        ("connect", None),
        ("configure_for_swing_speed_training", (45.0, 8)),
    ]


def test_disconnect_restores_rolling_buffer_mode(monkeypatch):
    """Leaving swing speed mode should put the OPS back into launch-monitor mode."""
    calls = []

    class FakeRadar:
        def __init__(self, port=None):
            self.port = port

        def restore_rolling_buffer_mode(self):
            calls.append("restore_rolling_buffer_mode")

        def disconnect(self):
            calls.append("disconnect")

    monkeypatch.setattr("openflight.swing_speed.OPS243Radar", FakeRadar)

    monitor = SwingSpeedMonitor(port="COM4")
    monitor.disconnect()

    assert calls == ["restore_rolling_buffer_mode", "disconnect"]


def test_select_swing_reading_uses_fastest_outbound_candidate():
    """Swing speed should prefer the fastest outbound return, not the strongest one."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=45.0)
    readings = [
        SpeedReading(
            speed=56.0,
            direction=Direction.OUTBOUND,
            magnitude=1200.0,
        ),
        SpeedReading(
            speed=103.0,
            direction=Direction.OUTBOUND,
            magnitude=180.0,
        ),
        SpeedReading(
            speed=120.0,
            direction=Direction.INBOUND,
            magnitude=900.0,
        ),
    ]

    selected = monitor._select_swing_reading(readings)  # pylint: disable=protected-access

    assert selected is readings[1]


def test_select_swing_reading_rejects_speeds_above_configured_max():
    """Impossible high candidates from OPS multi-report mode should be ignored."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=70.0, max_speed_mph=125.0)
    readings = [
        SpeedReading(
            speed=143.4,
            direction=Direction.OUTBOUND,
            magnitude=90.0,
        ),
        SpeedReading(
            speed=104.1,
            direction=Direction.OUTBOUND,
            magnitude=220.0,
        ),
    ]

    selected = monitor._select_swing_reading(readings)  # pylint: disable=protected-access

    assert selected is readings[1]


def _outbound(speed):
    return SpeedReading(speed=speed, direction=Direction.OUTBOUND)


def _inbound(speed):
    return SpeedReading(speed=speed, direction=Direction.INBOUND)


def test_select_swing_reading_ignores_inbound_candidates():
    """Inbound returns (e.g. the backswing) must never become the swing reading."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=30.0)

    selected = monitor._select_swing_reading(  # pylint: disable=protected-access
        [_inbound(95.0), _inbound(60.0)]
    )

    assert selected is None


def test_select_swing_reading_threshold_and_max_are_inclusive():
    """Readings exactly at the trigger threshold or the max ceiling qualify."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=30.0, max_speed_mph=125.0)
    select = monitor._select_swing_reading  # pylint: disable=protected-access

    at_threshold = _outbound(30.0)
    at_max = _outbound(125.0)

    assert select([at_threshold]) is at_threshold
    assert select([at_max]) is at_max
    assert select([_outbound(29.9)]) is None
    assert select([_outbound(125.1)]) is None


def test_select_swing_reading_without_max_accepts_high_speeds():
    """max_speed_mph=None disables the plausibility ceiling."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=30.0, max_speed_mph=None)
    fast = _outbound(190.0)

    assert monitor._select_swing_reading([fast]) is fast  # pylint: disable=protected-access


def test_select_swing_reading_skips_missing_candidates():
    """A None entry from the radar must not break candidate selection."""
    monitor = SwingSpeedMonitor(trigger_threshold_mph=30.0)
    valid = _outbound(70.0)

    assert monitor._select_swing_reading([None, valid]) is valid  # pylint: disable=protected-access
    assert monitor._select_swing_reading([]) is None  # pylint: disable=protected-access


class _FakeClock:
    """Deterministic stand-in for the time module; sleep advances the clock."""

    def __init__(self, start=1000.0):
        self.now = start

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _ScriptedRadar:
    """Feeds one scripted candidate list per poll, then goes quiet and stops the loop."""

    def __init__(self, clock, script, quiet_polls=1500):
        self.clock = clock
        self.script = list(script)
        self.quiet_polls = quiet_polls
        self.monitor = None

    def read_speed_candidates_nonblocking(self):
        if self.script:
            candidates = self.script.pop(0)
            for reading in candidates:
                reading.timestamp = self.clock.now
            return candidates
        self.quiet_polls -= 1
        if self.quiet_polls <= 0:
            self.monitor._running = False  # pylint: disable=protected-access
        return []

    def read_speed_nonblocking(self):
        return None


def _run_capture_loop(monkeypatch, script, monitor_cls=SwingSpeedMonitor, **monitor_kwargs):
    """Run the capture loop synchronously over a scripted reading sequence."""
    clock = _FakeClock()
    monkeypatch.setattr("openflight.swing_speed.time", clock)
    monitor = monitor_cls(**monitor_kwargs)
    radar = _ScriptedRadar(clock, script)
    radar.monitor = monitor
    monitor.radar = radar
    events = []
    monitor._event_callback = events.append  # pylint: disable=protected-access
    monitor._running = True  # pylint: disable=protected-access

    monitor._capture_loop()  # pylint: disable=protected-access

    return monitor, events


def test_capture_loop_emits_one_event_for_outbound_swing(monkeypatch):
    """A run of outbound readings followed by quiet becomes a single peak event."""
    script = [[_outbound(40.0)], [_outbound(70.0)], [_outbound(95.0)], [_outbound(80.0)]]

    monitor, events = _run_capture_loop(monkeypatch, script, trigger_threshold_mph=30.0)

    assert len(events) == 1
    event = events[0]
    assert event.peak_speed_mph == 95.0
    assert event.trigger_speed_mph == 40.0
    assert event.reading_count == 4
    assert event.mode == "swing-speed"
    assert monitor.get_events() == events


def test_capture_loop_ignores_inbound_only_motion(monkeypatch):
    """Inbound readings alone, however fast, must not produce a swing event."""
    script = [[_inbound(95.0)], [_inbound(97.0)], [_inbound(99.0)], [_inbound(90.0)]]

    monitor, events = _run_capture_loop(monkeypatch, script, trigger_threshold_mph=30.0)

    assert events == []
    assert monitor.get_events() == []


def test_capture_loop_peak_uses_outbound_when_inbound_is_faster(monkeypatch):
    """Mixed polls report the outbound peak even when an inbound candidate is faster."""
    script = [
        [_inbound(120.0), _outbound(50.0)],
        [_inbound(125.0), _outbound(88.0)],
        [_inbound(118.0), _outbound(72.0)],
    ]

    _, events = _run_capture_loop(monkeypatch, script, trigger_threshold_mph=30.0)

    assert len(events) == 1
    assert events[0].peak_speed_mph == 88.0
    assert events[0].reading_count == 3


def test_capture_loop_rejects_short_weak_motion(monkeypatch):
    """Fewer than min_readings below the single-reading peak is treated as noise."""
    script = [[_outbound(45.0)], [_outbound(50.0)]]

    _, events = _run_capture_loop(monkeypatch, script, trigger_threshold_mph=30.0)

    assert events == []


def test_capture_loop_accepts_single_strong_reading(monkeypatch):
    """One reading at or above single_reading_peak_mph is a valid swing."""
    script = [[_outbound(85.0)]]

    _, events = _run_capture_loop(monkeypatch, script, trigger_threshold_mph=30.0)

    assert len(events) == 1
    assert events[0].peak_speed_mph == 85.0
    assert events[0].reading_count == 1


class _InboundMonitor(SwingSpeedMonitor):
    """Subclass exercising the direction/mode extension points."""

    DIRECTION = Direction.INBOUND
    MODE = "test-inbound"

    def _configure_radar(self):
        self.radar.configured_by = "inbound"


def test_swing_speed_defaults_are_outbound_swing_mode():
    """Swing speed keeps its outbound direction and swing-speed mode tag."""
    assert SwingSpeedMonitor.DIRECTION == Direction.OUTBOUND
    assert SwingSpeedMonitor.MODE == "swing-speed"


def test_connect_uses_subclass_radar_configuration(monkeypatch):
    """connect() must route radar setup through the overridable hook."""

    class FakeRadar:
        def __init__(self, port=None):
            self.port = port
            self.configured_by = None

        def connect(self):
            pass

        def configure_for_swing_speed_training(self, **_kwargs):
            raise AssertionError("subclass must not get the swing-speed setup")

    monkeypatch.setattr("openflight.swing_speed.OPS243Radar", FakeRadar)
    monitor = _InboundMonitor()

    assert monitor.connect() is True
    assert monitor.radar.configured_by == "inbound"


def test_select_reading_follows_subclass_direction():
    """A subclass direction flips which candidates qualify."""
    monitor = _InboundMonitor(trigger_threshold_mph=30.0)
    inbound = _inbound(62.0)

    selected = monitor._select_swing_reading(  # pylint: disable=protected-access
        [_outbound(90.0), inbound]
    )

    assert selected is inbound


def test_capture_loop_with_subclass_direction_emits_tagged_event(monkeypatch):
    """The shared loop detects subclass-direction events and stamps the subclass mode."""
    script = [[_outbound(110.0), _inbound(48.0)], [_inbound(63.0)], [_inbound(57.0)]]

    _, events = _run_capture_loop(
        monkeypatch, script, monitor_cls=_InboundMonitor, trigger_threshold_mph=30.0
    )

    assert len(events) == 1
    assert events[0].peak_speed_mph == 63.0
    assert events[0].reading_count == 3
    assert events[0].mode == "test-inbound"
