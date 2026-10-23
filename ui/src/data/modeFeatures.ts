import type { MessageKey } from '../i18n/en';
import type { TriggerStatus } from '../types/shot';

export type MonitorMode = TriggerStatus['mode'];

/** What the Live panel offers for choosing the club or implement. */
export type PickerFeature =
  | { kind: 'club'; titleKey: MessageKey; changeKey: MessageKey; wide: false }
  | { kind: 'implement'; titleKey: MessageKey; changeKey: MessageKey; wide: true }
  | { kind: 'none'; labelKey: MessageKey | null };

export interface SpeedRange {
  min: number;
  max: number;
}

/** Lower/upper gates for modes that stream OPS speed reports instead of capturing a buffer. */
export interface SpeedGateTuning {
  lower: SpeedRange;
  upper: SpeedRange;
  hint: string;
  mockNote: string;
}

export interface ModeFeatures {
  picker: PickerFeature;
  /** Null hides the mock Simulate button. */
  simulateLabelKey: MessageKey | null;
  /** Null means the golf min-speed and magnitude filters, which are disabled in mock mode. */
  speedGates: SpeedGateTuning | null;
}

// Until the server reports its mode, show nothing mode-specific so no golf UI flashes.
const CONNECTING_FEATURES: ModeFeatures = Object.freeze({
  picker: Object.freeze({ kind: 'none', labelKey: null }),
  simulateLabelKey: null,
  speedGates: null,
});

const GOLF_FEATURES: ModeFeatures = Object.freeze({
  picker: Object.freeze({ kind: 'club', titleKey: 'app.selectClub', changeKey: 'app.changeClub', wide: false }),
  simulateLabelKey: 'app.simulateShot',
  speedGates: null,
});

const SWING_SPEED_FEATURES: ModeFeatures = Object.freeze({
  picker: Object.freeze({
    kind: 'implement',
    titleKey: 'app.selectImplement',
    changeKey: 'app.changeImplement',
    wide: true,
  }),
  simulateLabelKey: 'app.simulateSwing',
  speedGates: Object.freeze({
    lower: Object.freeze({ min: 30, max: 100 }),
    upper: Object.freeze({ min: 90, max: 170 }),
    hint: 'Lower speed updates the OPS filter; upper speed rejects implausible high swing-speed outliers.',
    mockNote: 'Mock swing speed sliders shape simulated reps only',
  }),
});

// Both ranges contain the server's fastpitch defaults (30 and 80 mph).
const PITCH_SPEED_FEATURES: ModeFeatures = Object.freeze({
  picker: Object.freeze({ kind: 'none', labelKey: 'app.pitchSpeed' }),
  simulateLabelKey: 'app.simulatePitch',
  speedGates: Object.freeze({
    lower: Object.freeze({ min: 15, max: 60 }),
    upper: Object.freeze({ min: 50, max: 100 }),
    hint: 'Lower speed updates the OPS filter; upper speed rejects implausible high pitch-speed outliers.',
    mockNote: 'Mock pitch speed sliders shape simulated pitches only',
  }),
});

const FEATURES_BY_MODE: Readonly<Record<MonitorMode, ModeFeatures>> = Object.freeze({
  connecting: CONNECTING_FEATURES,
  'rolling-buffer': GOLF_FEATURES,
  mock: GOLF_FEATURES,
  'swing-speed': SWING_SPEED_FEATURES,
  'pitch-speed': PITCH_SPEED_FEATURES,
});

/**
 * Decide what the UI shows for the server's monitor mode. A mode this UI does
 * not know (e.g. a newer server) falls back to the golf launch monitor.
 */
export function getModeFeatures(mode: string): ModeFeatures {
  return Object.hasOwn(FEATURES_BY_MODE, mode) ? FEATURES_BY_MODE[mode as MonitorMode] : GOLF_FEATURES;
}
