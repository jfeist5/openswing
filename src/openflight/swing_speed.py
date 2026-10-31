"""Swing speed training monitor using OPS243 speed streaming."""

import logging
import statistics
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from .ops243 import Direction, OPS243Radar, SpeedReading
from .session_logger import log_session_error

logger = logging.getLogger("openflight.swing_speed")

# Fastpitch radar-gun limits: below youth pitch speeds, above the women's record.
PITCH_TRIGGER_THRESHOLD_MPH = 30.0
PITCH_MAX_SPEED_MPH = 80.0
PITCH_IMPLEMENT = "pitch"
PITCH_IMPLEMENT_LABEL = "Pitch"
# Pitch gate, from bench captures of hand moves on an OPS243-A (noise floor
# about 20-28); validate against real tosses at pitching distance.
PITCH_MIN_MAGNITUDE = 50.0
PITCH_DOMINANT_FRACTION = 0.10


@dataclass
class SwingSpeedEvent:
    """A single club-only swing speed training rep."""

    peak_speed_mph: float
    timestamp: datetime
    duration_ms: float
    reading_count: int
    trigger_speed_mph: float
    peak_magnitude: Optional[float] = None
    training_implement: str = "driver"
    training_implement_label: str = "Driver"
    profile_id: str = ""
    profile_name: str = ""
    unit: str = "mph"
    mode: str = "swing-speed"


class SwingSpeedMonitor:
    """Monitor OPS243 speed readings and emit club-only swing speed reps."""

    # Must match the direction filter sent by _configure_radar().
    DIRECTION = Direction.OUTBOUND
    MODE = "swing-speed"
    LOG_TAG = "[SWING_SPEED]"
    EVENT_NOUN = "Swing"

    def __init__(
        self,
        port: Optional[str] = None,
        trigger_threshold_mph: float = 30.0,
        max_speed_mph: Optional[float] = 130.0,
        min_readings: int = 3,
        single_reading_peak_mph: float = 60.0,
        num_reports: int = 8,
        end_quiet_ms: float = 1000.0,
        cooldown_ms: float = 750.0,
        rejected_cooldown_ms: float = 100.0,
        poll_interval_ms: float = 2.0,
    ):
        self.radar = OPS243Radar(port=port)
        self.trigger_threshold_mph = trigger_threshold_mph
        self.max_speed_mph = max_speed_mph
        self.min_readings = min_readings
        self.single_reading_peak_mph = single_reading_peak_mph
        self.num_reports = num_reports
        self.end_quiet_ms = end_quiet_ms
        self.cooldown_ms = cooldown_ms
        self.rejected_cooldown_ms = rejected_cooldown_ms
        self.poll_interval_ms = poll_interval_ms

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._event_callback: Optional[Callable[[SwingSpeedEvent], None]] = None
        self._live_callback: Optional[Callable[[SpeedReading], None]] = None
        self._events: List[SwingSpeedEvent] = []
        self.training_implement = "driver"
        self.training_implement_label = "Driver"

    def connect(self) -> bool:
        """Connect to the radar and configure CW speed reporting for training.

        Uses the dedicated training path rather than the launch monitor's
        configure_for_speed_trigger(), which exists to detect a swing and hand
        off to the rolling buffer. Training never captures a rolling buffer.
        """
        self.radar.connect()
        self._configure_radar()
        logger.info(
            "%s Monitor ready (threshold=%.1f mph, max=%s, reports=%d, end_quiet=%.0fms)",
            self.LOG_TAG,
            self.trigger_threshold_mph,
            "%.1f mph" % self.max_speed_mph if self.max_speed_mph is not None else "off",
            self.num_reports,
            self.end_quiet_ms,
        )
        return True

    def _configure_radar(self):
        """Apply this mode's CW speed-reporting setup to the connected radar."""
        self.radar.configure_for_swing_speed_training(
            min_speed_mph=self.trigger_threshold_mph,
            num_reports=self.num_reports,
        )

    def disconnect(self):
        """Disconnect from the radar."""
        self.stop()
        try:
            self.radar.restore_rolling_buffer_mode()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("%s Failed to restore rolling buffer mode: %s", self.LOG_TAG, exc)
        self.radar.disconnect()

    def get_radar_info(self) -> dict:
        """Get radar module information."""
        return self.radar.get_info()

    def start(
        self,
        event_callback: Optional[Callable[[SwingSpeedEvent], None]] = None,
        live_callback: Optional[Callable[[SpeedReading], None]] = None,
    ):
        """Start monitoring for swing speed reps."""
        self._event_callback = event_callback
        self._live_callback = live_callback
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("%s Monitor started", self.LOG_TAG)

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("%s Monitor stopped", self.LOG_TAG)

    def get_events(self) -> List[SwingSpeedEvent]:
        """Return a copy of recorded swing speed events."""
        return list(self._events)

    def get_shots(self) -> list:
        """Return no launch-monitor shots for compatibility with server handlers."""
        return []

    def clear_session(self):
        """Clear recorded swing speed events."""
        self._events.clear()

    def set_club(self, _club):
        """Ignore club selection changes in club-only training mode."""
        return None

    def set_training_implement(self, implement: str, label: str):
        """Set the training implement stamped onto future swing speed reps."""
        self.training_implement = implement
        self.training_implement_label = label

    def get_session_stats(self) -> dict:
        """Get summary statistics for the current swing speed session."""
        if not self._events:
            return {
                "swing_count": 0,
                "best_speed_mph": 0,
                "avg_speed_mph": 0,
                "last_speed_mph": 0,
            }

        speeds = [event.peak_speed_mph for event in self._events]
        return {
            "swing_count": len(self._events),
            "best_speed_mph": round(max(speeds), 1),
            "avg_speed_mph": round(statistics.mean(speeds), 1),
            "last_speed_mph": round(speeds[-1], 1),
        }

    def _capture_loop(self):
        """Capture speed-stream readings and group them into swing events."""
        active_readings: List[SpeedReading] = []
        trigger_speed = 0.0
        swing_start = 0.0
        last_active = 0.0
        cooldown_until = 0.0

        while self._running:
            try:
                now = time.time()
                reading = self._next_reading()
                if reading and self._live_callback:
                    self._live_callback(reading)

                qualifies = self._reading_qualifies(reading)

                if now < cooldown_until:
                    time.sleep(self.poll_interval_ms / 1000.0)
                    continue

                if qualifies:
                    if not active_readings:
                        swing_start = reading.timestamp or now
                        trigger_speed = reading.speed
                        logger.info(
                            "%s %s started at %.1f mph",
                            self.LOG_TAG,
                            self.EVENT_NOUN,
                            trigger_speed,
                        )
                    active_readings.append(reading)
                    last_active = reading.timestamp or now
                elif active_readings and (now - last_active) * 1000.0 >= self.end_quiet_ms:
                    peak_speed = max(reading.speed for reading in active_readings)
                    strong_single_peak = peak_speed >= self.single_reading_peak_mph
                    if len(active_readings) < self.min_readings and not strong_single_peak:
                        logger.info(
                            "%s Ignored short motion: %d readings, peak=%.1f mph",
                            self.LOG_TAG,
                            len(active_readings),
                            peak_speed,
                        )
                        active_readings = []
                        cooldown_until = now + self.rejected_cooldown_ms / 1000.0
                        continue

                    event = self._build_event(
                        readings=active_readings,
                        trigger_speed=trigger_speed,
                        swing_start=swing_start,
                        swing_end=last_active,
                    )
                    self._events.append(event)
                    logger.info(
                        "%s %s detected: peak=%.1f mph, readings=%d",
                        self.LOG_TAG,
                        self.EVENT_NOUN,
                        event.peak_speed_mph,
                        event.reading_count,
                    )
                    if self._event_callback:
                        self._event_callback(event)

                    active_readings = []
                    cooldown_until = now + self.cooldown_ms / 1000.0

                time.sleep(self.poll_interval_ms / 1000.0)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("%s Capture loop error: %s", self.LOG_TAG, exc, exc_info=True)
                log_session_error(
                    f"{self.EVENT_NOUN} speed capture loop error",
                    component="swing_speed_monitor",
                    exc=exc,
                )
                time.sleep(1.0)

    def _next_reading(self) -> Optional[SpeedReading]:
        """Poll the radar once and return the reading that represents this poll, if any."""
        readings = self.radar.read_speed_candidates_nonblocking()
        if not readings:
            single_reading = self.radar.read_speed_nonblocking()
            readings = [single_reading] if single_reading else []
        return self._select_swing_reading(readings)

    def _select_swing_reading(self, readings: List[SpeedReading]) -> Optional[SpeedReading]:
        """Select the fastest qualifying candidate for this mode's direction."""
        qualifying = [reading for reading in readings if self._reading_qualifies(reading)]
        if not qualifying:
            return None
        return max(qualifying, key=lambda reading: reading.speed)

    def _reading_qualifies(self, reading: Optional[SpeedReading]) -> bool:
        """Return true for a reading in this mode's direction and speed window."""
        return (
            reading is not None
            and reading.direction == self.DIRECTION
            and reading.speed >= self.trigger_threshold_mph
            and self._within_max_speed(reading.speed)
        )

    def _within_max_speed(self, speed_mph: float) -> bool:
        """Return true when a speed is below the configured plausible ceiling."""
        return self.max_speed_mph is None or speed_mph <= self.max_speed_mph

    def _build_event(
        self,
        readings: List[SpeedReading],
        trigger_speed: float,
        swing_start: float,
        swing_end: float,
    ) -> SwingSpeedEvent:
        """Create a SwingSpeedEvent from the completed swing window."""
        peak = max(readings, key=lambda item: item.speed)
        peak_magnitude = max(
            (reading.magnitude for reading in readings if reading.magnitude is not None),
            default=None,
        )
        return SwingSpeedEvent(
            peak_speed_mph=peak.speed,
            timestamp=datetime.fromtimestamp(peak.timestamp or time.time()),
            duration_ms=max(0.0, (swing_end - swing_start) * 1000.0),
            reading_count=len(readings),
            trigger_speed_mph=trigger_speed,
            peak_magnitude=peak_magnitude,
            training_implement=self.training_implement,
            training_implement_label=self.training_implement_label,
            unit=peak.unit,
            mode=self.MODE,
        )


class PitchSpeedMonitor(SwingSpeedMonitor):
    """Monitor inbound OPS243 speed readings and emit fastpitch pitch speeds.

    Reuses the swing-speed capture loop: each pitch is reported at the peak
    inbound reading, like a radar gun, and never uses the rolling buffer.
    Unlike swing speed, each radar report is gated by its strongest echo, so
    ghosts of outbound motion and faint stray peaks cannot become pitches.
    """

    DIRECTION = Direction.INBOUND
    MODE = "pitch-speed"
    LOG_TAG = "[PITCH_SPEED]"
    EVENT_NOUN = "Pitch"

    def __init__(
        self,
        port: Optional[str] = None,
        trigger_threshold_mph: float = PITCH_TRIGGER_THRESHOLD_MPH,
        max_speed_mph: Optional[float] = PITCH_MAX_SPEED_MPH,
        min_magnitude: float = PITCH_MIN_MAGNITUDE,
        **kwargs,
    ):
        if min_magnitude < 0:
            raise ValueError("min_magnitude must not be negative")
        super().__init__(
            port=port,
            trigger_threshold_mph=trigger_threshold_mph,
            max_speed_mph=max_speed_mph,
            **kwargs,
        )
        self.min_magnitude = min_magnitude
        self.training_implement = PITCH_IMPLEMENT
        self.training_implement_label = PITCH_IMPLEMENT_LABEL

    def _next_reading(self) -> Optional[SpeedReading]:
        """Gate each report separately, then keep the fastest accepted reading of this poll."""
        accepted = [
            reading
            for reading in map(
                self._select_report_reading, self.radar.read_speed_reports_nonblocking()
            )
            if reading is not None
        ]
        if not accepted:
            return None
        return max(accepted, key=lambda reading: reading.speed)

    def _select_report_reading(self, report: List[SpeedReading]) -> Optional[SpeedReading]:
        """Pick a pitch reading from one radar report, or None if the report is not a pitch.

        The strongest echo decides the report: it must be inbound and above the
        noise floor. Then the fastest qualifying inbound candidate at least
        PITCH_DOMINANT_FRACTION as strong as that echo wins.
        """
        candidates = [reading for reading in report if reading.magnitude is not None]
        if not candidates:
            return None
        dominant = max(candidates, key=lambda reading: reading.magnitude)
        if dominant.direction != Direction.INBOUND or dominant.magnitude < self.min_magnitude:
            return None
        floor = PITCH_DOMINANT_FRACTION * dominant.magnitude
        eligible = [
            reading
            for reading in candidates
            if reading.magnitude >= floor and self._reading_qualifies(reading)
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda reading: reading.speed)

    def _configure_radar(self):
        """Apply the pitch speed setup (both directions reported) to the connected radar."""
        self.radar.configure_for_pitch_speed(
            min_speed_mph=self.trigger_threshold_mph,
            num_reports=self.num_reports,
        )
