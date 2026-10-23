# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is my personal fork of OpenFlight for softball, called openswing (hitting exit velocity and pitch speed). Golf support should keep working. I’m new to this codebase, so explain changes before making them and keep them small.

OpenFlight is a DIY golf launch monitor using the OPS243-A Doppler radar and K-LD7 angle radars (deprecated — superseded by a more capable radar chip; K-LD7 support is kept for existing builds only). It measures ball speed, club speed, launch angle, club path, spin rate, and carry distance.

The Python package is `openflight` (`src/openflight/`), even though the checkout directory may be named differently. It runs on a Raspberry Pi; macOS is the other supported dev platform. `[tool.uv] environments` in `pyproject.toml` excludes Windows, so `uv sync`/`uv run` will not resolve on a Windows host.

## Softball Fork (openswing)

**Scope:** fastpitch softball only (43 ft pitching distance). Slowpitch is out of scope.

**Hardware owned:** Raspberry Pi 5 (8 GB), OPS243-A, IWR6843 (TI IWR6843LEVM), two K-LD7s, SEN-14262 sound sensor, 7" touchscreen.

**Mount (same as a Full Swing KIT):** about 10 ft behind home plate, centered, about 8 ft high, looking toward the pitcher. From there, pitches are **inbound** (negative FFT frequencies, OPS `R+`) and batted balls are **outbound**.

**Constraints:**
- Golf mode must keep working.
- Never delete code. That includes sim forwarding, carry/ballistics, spin, and launch angle. Hide features that don't apply in a softball mode instead.
- Keep all IWR6843 and K-LD7 angle-radar code. The IWR6843 (possibly also the K-LD7s) is the planned launch-angle source.

**Goals by mode:**

| Mode | Metrics | Status |
|---|---|---|
| Pitching | Velocity, session stats, pitch type, spin rate (see the pitch metric plan below) | Velocity done. Pitch screens in progress (step 4). |
| Hitting | Exit velocity, launch angle, carry | Later. Includes a view showing ball flight on a softball field. |

- **Pitch-speed mode is for bullpens and pitching practice only, with no batter.** Hitting will be a separate mode later.
- **Pitch metric plan, in this order:**
  1. Velocity (done).
  2. Session stats: pitch count, average, max, and velocity trend over the session (for fatigue).
  3. Pitch-type tagging, using the pitch-type picker below, with stats split by pitch type.
  4. Spin rate (experimental): needs the retuned fastpitch RPM range and a capture trigger during flight, not the glove pop (see "Pitch spin" below).
  - Future, maybe: pitch location at the plate and approach angle, using the IWR6843.
- **Pitch-speed mode:** hide the club picker and golf sim forwarding. Swing-speed mode is the precedent:
  - `swing_speed.py` streams OPS CW speed reports and takes the peak of each event, like a radar gun. It never uses the rolling buffer.
  - `on_swing_speed_detected` in `server.py` never calls the sim connectors.
  - The UI decides what each mode shows through `getModeFeatures` in `ui/src/data/modeFeatures.ts`.
- **Pitch-speed design decisions (agreed):**
  1. Generalize the swing-speed monitor with direction and mode settings. `PitchSpeedMonitor` is a thin subclass, so the server's existing `isinstance(SwingSpeedMonitor)` checks keep working. Tests must pin swing-speed behavior unchanged.
  2. Add a separate `configure_for_pitch_speed` in `ops243.py`: inbound only (`R+`) and a finer FFT than swing-speed's 256-point (~1.6 mph per bin). Steps shared with the swing-speed setup move into one private helper. Each mode keeps its own setup so tuning one can't change another.
  3. In the UI, a single mode-to-features helper decides what each mode shows (club picker, simulate-button label, etc.). It replaces the scattered `isSwingSpeedMode` checks.
  4. Render pitch shots as pitches, not golf shots: Live tiles, Stats, Shots list, TV display, and CSV export (the `isSwingSpeedShot` checks). Add Playwright pitch-mode tests at all three kiosk sizes (800×400, 800×480, 1024×600). Playwright runs against the real Python server in mock mode (`ui/playwright.config.ts`), not `ui/mock-server/`, so pitch tests need a backend started with `--mock-pitch-speed`. Also fix the golf screen that flashes on page load before the server reports its mode. Leave room on the pitch screens for velocity trend, pitch type, and spin rate, but don't build them yet.
- **Future: pitch-type picker.** Pick fastball, rise, drop, curve, screw, or change-up before a pitch, and tag each pitch with it so stats can be broken down by pitch type. Needs a server-side pitch-type list (like `TRAINING_IMPLEMENT_LABELS`) and a picker in pitch mode, which has none after step 3.
- **Future: mode-select menu on startup.** Choose Pitching, Swing training, Hitting, or Golf from the UI so coaches don't need command-line flags. Ideally switch modes without restarting, reconfiguring the radar for the selected mode. Notes for when it's built:
  - `start_monitor` in `server.py` already stops the current monitor before starting another, and the speed-streaming monitors call `restore_rolling_buffer_mode()` on disconnect.
  - Switching back to Golf at runtime is a mode transition on the OPS243-A, which can flip HOST_INT pin mode (see "Radar Setup"). The sound trigger must be verified on hardware after a switch, or the switch may need a radar power cycle.
- **Pitch spin:** needs two changes.
  - A retuned RPM range. The processor searches only 2,000–12,000 RPM (`SPIN_MIN/MAX_SEAM_HZ`) and uses golf spin priors.
  - A different capture trigger. The 4096-sample rolling buffer holds about 136 ms at 30 ksps, a pitch flies for about 0.5 s, and a glove-pop sound trigger fires only at the end of the flight.
- **Carry:** keep the model, but make ball size, mass, and drag configurable. `ballistics.py` hard-codes a USGA golf ball (`BALL_MASS_KG`, `BALL_RADIUS_M`).
- **Hitting launch angle:** planned from the IWR6843 with the softball mount geometry.

**Geometry consequences** (estimates from the mount above; verify on hardware):
- **Pitch near release:** the release point is about 48–50 ft from the radar and about 6 ft below it, so the line-of-sight angle is about 7°. The radial reading is less than 1% low.
- **Pitch at the plate:** the angle is about 30°, so the reading is about 13% low. The peak radial reading therefore occurs near release, which is the conventional pitch speed. Aim the OPS beam at the release point, not at the plate.
- **Batted ball at contact:** the line of sight slopes about 25–30° *downward* while the ball rises, so early radial readings can be 25%+ below true exit velocity. They only approach it about 20–30 ft out, past the ~68 ms of post-trigger buffer at the default `S#16`. Exit velocity will need launch-angle-based correction, a different pre/post-trigger split, or both.
  - `speed_correction.py` models only the golf geometry: radar below and behind a tee, vertical angle only.
- **Golf-tuned assumptions** that won't transfer to softball as-is:
  - **IWR6843:** the validated mount is about 6 in off the floor, tilted up about 10°, about 1.4 m from the tee, with a net about 4 m away. LCMF-v1 constants are frozen; changing them requires a new estimator version and validation.
  - **K-LD7:** the geometry assumes the ball about 4 in below the radar, launch angles of 0–45°, and at most 150 ms of flight (`kld7/geometry.py`).
  - **K-LD7 and OPS243 interference:** both run at 24 GHz and can interfere. The IWR6843 runs at 60 GHz.

## Development Rules

- **Read `AGENTS.md` (and `ui/AGENTS.md` for UI work) — its rules are mandatory.** It covers change scope, validation, and the PR rules that CI enforces in `.github/workflows/anti-slop.yml` and `pr-checks.yml`: conventional PR titles, ≤50 files / ≤2,000 changed lines, ≤25 added comment lines, a trailing newline on every file, and the PR template filled in. Never describe mock or simulated runs as hardware validation.
- **Always use `uv` for Python commands.** Use `uv run` to execute Python tools (pytest, pylint, ruff, etc.). Never use bare `python`, `pip`, `pytest`, etc.
- **Update `pyproject.toml` when adding dependencies.** If new Python packages are introduced, add them to the appropriate dependency list in `pyproject.toml`.
- **Bug reports: write a failing test first.** When the user reports a bug, write a test that reproduces and confirms the bug before investigating or fixing it.
- **Default startup is `scripts/start-kiosk.sh`.** Assume the project is started via this script unless told otherwise. It handles venv activation, UI build, and server launch.

# Claude Code Prompt for Plan Mode

Review this plan thoroughly before making any code changes. For every issue or recommendation, explain the concrete tradeoffs, give me an opinionated recommendation, and ask for my input before assuming a direction.

My engineering preferences (use these to guide your recommendations):

- DRY is important—flag repetition aggressively.
- Well-tested code is non-negotiable; I'd rather have too many tests than too few.
- I want code that's "engineered enough" — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity).
- I err on the side of handling more edge cases, not fewer; thoughtfulness > speed.
- Bias toward explicit over clever.

## 1. Architecture review

Evaluate:

- Overall system design and component boundaries.
- Dependency graph and coupling concerns.
- Data flow patterns and potential bottlenecks.
- Scaling characteristics and single points of failure.
- Security architecture (auth, data access, API boundaries).

## 2. Code quality review

Evaluate:

- Code organization and module structure.
- DRY violations—be aggressive here.
- Error handling patterns and missing edge cases (call these out explicitly).
- Technical debt hotspots.
- Areas that are over-engineered or under-engineered relative to my preferences.

## 3. Test review

Evaluate:

- Test coverage gaps (unit, integration, e2e).
- Test quality and assertion strength.
- Missing edge case coverage—be thorough.
- Untested failure modes and error paths.

## 4. Performance review

Evaluate:

- N+1 queries and database access patterns.
- Memory-usage concerns.
- Caching opportunities.
- Slow or high-complexity code paths.

**For each issue you find**

For every specific issue (bug, smell, design concern, or risk):

- Describe the problem concretely, with file and line references.
- Present 2–3 options, including "do nothing" where that's reasonable.
- For each option, specify: implementation effort, risk, impact on other code, and maintenance burden.
- Give me your recommended option and why, mapped to my preferences above.
- Then explicitly ask whether I agree or want to choose a different direction before proceeding.

**Workflow and interaction**

- Do not assume my priorities on timeline or scale.
- After each section, pause and ask for my feedback before moving on.

---

BEFORE YOU START:
Ask if I want one of two options:
1/ BIG CHANGE: Work through this interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 4 top issues in each section.
2/ SMALL CHANGE: Work through interactively ONE question per review section

FOR EACH STAGE OF REVIEW: output the explanation and pros and cons of each stage's questions AND your opinionated recommendation and why, and then use AskUserQuestion. Also NUMBER issues and then give LETTERS for options and when using AskUserQuestion make sure each option clearly labels the issue NUMBER and option LETTER so the user doesn't get confused. Make the recommended option always the 1st option.

## Commands

### Python Backend

```bash
# Run tests
uv run pytest tests/ -v

# Run single test file
uv run pytest tests/test_launch_monitor.py -v

# Run single test
uv run pytest tests/test_launch_monitor.py::TestLaunchMonitor::test_name -v

# Lint (must score 9.0+)
uv run pylint src/openflight/ --fail-under=9

# Format check
uv run ruff check src/openflight/
uv run ruff format --check src/openflight/
```

### React UI (in /ui directory)

Kiosk / touch conventions for agents: see `ui/AGENTS.md`.

```bash
npm run dev           # Vite dev server with hot reload
npm run dev:mock      # Vite + mock WebSocket server (ui/mock-server/), no backend needed
npm run build         # Production build (tsc -b && vite build)
npm run lint          # ESLint
npm run format:check  # Prettier check (enforced in CI)
npm test              # Vitest unit tests
npm run test:e2e      # Playwright E2E (kiosk sizes 800×400, 800×480, 1024×600)
```

### Makefile shortcuts and docs

`make install` (uv sync --group dev + npm install), `make test`, `make lint` (ruff + pylint + ESLint), `make format`, `make dev` (mock mode), `make hooks` (pre-commit: ruff, pylint, eslint). Docs: `make docs` (zensical live server) and `make docs-build` (strict build that fails on broken internal links; `tests/test_doc_references.py` also checks doc references).

### Radar Setup (One-Time)

The OPS243-A must have rolling buffer mode saved to persistent memory for hardware triggers to work.
This is due to a firmware bug where HOST_INT pin mode switches when transitioning modes at runtime.

```bash
# Configure and save rolling buffer mode to flash (one-time)
uv run python scripts/hardware-test/test_rolling_buffer_persist.py --setup
# Power cycle the radar (unplug USB, wait 3s, replug)
uv run python scripts/hardware-test/test_rolling_buffer_persist.py --test
```

### Running the Application

```bash
scripts/start-kiosk.sh              # Default: rolling buffer + sound trigger
scripts/start-kiosk.sh --mock       # Development mode without hardware
scripts/start-kiosk.sh --kld7                          # With K-LD7 angle radars (deprecated; auto-detects horizontal)
scripts/start-kiosk.sh --swing-speed  # Swing speed training (air swings, no sound trigger)
scripts/start-kiosk.sh --iwr6843 --ops-port /dev/ttyAMA0 \
  --iwr6843-tee-m <m> --iwr6843-net-m <m> --iwr6843-tilt-deg <deg> \
  --iwr6843-radar-height-m <m> --iwr6843-ball-height-m <m>   # IWR6843 angle radar; geometry must be measured per rig
```

### Sound Trigger Testing

```bash
# Test persistent rolling buffer + hardware trigger (recommended)
uv run python scripts/hardware-test/test_rolling_buffer_persist.py --test

# Test direct hardware sound trigger (GATE → HOST_INT)
uv run python scripts/hardware-test/test_sound_trigger_hardware.py
```

## Architecture

```
React UI (WebSocket) ──► Flask Server ──► RollingBufferMonitor ──► OPS243Radar
                              │                │
                              │                └── SoundTrigger (SEN-14262 → HOST_INT)
                              │
                              ├── IWR6843Runtime (optional, 60 GHz → launch angle & club path)
                              ├── KLD7Tracker (vertical/horizontal, deprecated)
                              ├── Ballistics Simulator (RK4 trajectory & carry)
                              ├── SimConnectors (OpenGolfSim, GSPro, E6, etc.)
                              ├── CloudSync (optional telemetry & session backup)
                              │
                              └── SessionLogger (JSONL files)
```

### Data Flow

1. **SoundTrigger** detects club impact via SEN-14262 GATE → OPS243 HOST_INT
2. **OPS243Radar** (`ops243.py`) dumps rolling buffer I/Q data (4096 samples)
3. **RollingBufferProcessor** (`rolling_buffer/processor.py`) runs FFT + mode-based speed extraction
4. Creates `Shot` object with ball_speed, club_speed, spin, carry
5. **IWR6843** (or legacy **KLD7Trackers**) extracts launch angle and club path from radar measurements
   - When an angle radar is enabled, `server.py` then applies a cosine correction to ball speed (`speed_correction.py`), because the OPS243 reads only the radial component. The raw value is kept in `ball_speed_raw_mph`. Ordering matters: the angle radars anchor to the *raw* speed, and calculated spin and carry use the *corrected* speed.
6. **Ballistics engine** (`ballistics.py`) computes trajectory and carry distance
7. **Flask server** (`server.py`) emits WebSocket "shot" event and forwards to connected simulator software
8. **React UI** (`ui/src/`) renders shot data

### Key Modules

- `ops243.py` - OPS243 radar driver, rolling buffer capture, I/Q processing
- `clubs/` - Built-in club types and immutable physics defaults
- `launch_monitor.py` - Shot dataclass and carry estimation
- `ballistics.py` - Numerical ballistic trajectory simulation (drag + Magnus RK4)
- `iwr6843/` - TI IWR6843 mmWave radar driver, L3 raw dump parser, LCMF-v1 launch angle & club path
- `inclinometer.py` - LIS3DH accelerometer tilt compensation service
- `sim/` - Simulator connectors (OpenGolfSim, GSPro, E6 Connect, Garmin) and network transports
- `cloud/` - Telemetry, cloud configuration, session upload, and push error handling
- `rolling_buffer/` - Trigger strategies, I/Q processor, spin detection
- `kld7/` - K-LD7 angle radar (deprecated hardware): RADC streaming, phase interferometry, dual-radar support
- `kld7/radc.py` - FFT, CFAR detection, per-bin angle extraction from raw ADC
- `server.py` - Flask server, AppState runtime management, staged shot processing pipeline
- `session_logger.py` - JSONL logging for post-session analysis

### Processing Mode

**Rolling Buffer** is the default and only production mode. The OPS243-A continuously buffers I/Q data. When the sound trigger fires, the buffer is dumped and analyzed for ball speed, club speed, and spin rate. IWR6843 or legacy K-LD7 data is correlated via the OPS243 impact timestamp.

Inside `RollingBufferProcessor.process_capture`, one FFT pass at a 32-sample step yields two timelines: a non-overlapping 128-step timeline (~234 Hz) and the full overlapping one (~937 Hz).
- **Ball speed** comes from the non-overlapping timeline. It is the fastest 1-mph bucket that repeats in at least two windows, *not* the max, so single-window noise spikes are rejected.
- **Club speed, impact time, and spin** use the overlapping timeline.
- **FFT direction:** positive frequencies are outbound (ball/club moving away from the radar) and negative frequencies are inbound.

## Key Constants

- Sample rate: 30,000 Hz
- FFT window: 128 samples, zero-padded to 4096
- DC mask: 150 bins (~15 mph exclusion zone)
- Min ball speed: 15 mph (35 mph for speed-triggered mode)
- K-LD7 OS-CFAR threshold factor: 8.0 (deprecated hardware)

## Session Logging

Logs written to `~/openflight_sessions/session_*.jsonl` with entry types:

- `session_start`, `session_end` - Session metadata
- `reading_accepted` - Individual radar readings
- `shot_detected` - Detected shots with metrics (ball_speed, club_speed, spin_rpm, carry_spin_adjusted)
- `iq_reading` - I/Q streaming detections with SNR/CFAR data
- `iq_blocks` - Raw I/Q data for post-session analysis
- `trigger_event` - Trigger accept/reject with latency (for rolling buffer mode)
- `rolling_buffer_capture` - Raw I/Q samples (4096 each) for offline analysis

## Sound Trigger Hardware

The SparkFun SEN-14262 detects club impact and triggers the OPS243-A via HOST_INT.

**Wiring:**

```
SEN-14262 GATE → OPS243-A HOST_INT (J3 Pin 3)
SEN-14262 VCC  → Pi 3.3V
SEN-14262 GND  → Pi GND (shared with OPS243-A)
```

A through-hole resistor must be soldered into **R17** on the SEN-14262 to reduce preamp gain at 3.3V (47kΩ recommended, lower for noisy environments).

See [docs/build/sound-trigger.md](docs/build/sound-trigger.md) for full instructions.

**Trigger Latency:**
| Trigger | Latency | Description |
|---------|---------|-------------|
| `sound` | ~10μs | Hardware: SEN-14262 GATE → HOST_INT |
| `speed` | ~5-6ms | Radar speed detection triggers capture |
