import { describe, expect, it } from 'vitest';
import { getModeFeatures, type ModeFeatures } from './modeFeatures';

function isDeepFrozen(value: unknown): boolean {
  if (value === null || typeof value !== 'object') return true;
  return Object.isFrozen(value) && Object.values(value).every(isDeepFrozen);
}

function gateContains(features: ModeFeatures, lowerMph: number, upperMph: number): boolean {
  const gates = features.speedGates;
  if (!gates) return false;
  return (
    gates.lower.min <= lowerMph &&
    lowerMph <= gates.lower.max &&
    gates.upper.min <= upperMph &&
    upperMph <= gates.upper.max
  );
}

describe('getModeFeatures', () => {
  it.each(['rolling-buffer', 'mock'])('gives the golf %s mode the club picker and golf filters', (mode) => {
    expect(getModeFeatures(mode)).toEqual({
      picker: { kind: 'club', titleKey: 'app.selectClub', changeKey: 'app.changeClub', wide: false },
      simulateLabelKey: 'app.simulateShot',
      speedGates: null,
    });
  });

  it('gives swing speed the wide implement picker and swing gates', () => {
    const features = getModeFeatures('swing-speed');

    expect(features.picker).toEqual({
      kind: 'implement',
      titleKey: 'app.selectImplement',
      changeKey: 'app.changeImplement',
      wide: true,
    });
    expect(features.simulateLabelKey).toBe('app.simulateSwing');
    expect(features.speedGates?.lower).toEqual({ min: 30, max: 100 });
    expect(features.speedGates?.upper).toEqual({ min: 90, max: 170 });
  });

  it('gives pitch speed no picker, a pitch label, and fastpitch gates', () => {
    const features = getModeFeatures('pitch-speed');

    expect(features.picker).toEqual({ kind: 'none', labelKey: 'app.pitchSpeed' });
    expect(features.simulateLabelKey).toBe('app.simulatePitch');
    expect(features.speedGates?.lower).toEqual({ min: 15, max: 60 });
    expect(features.speedGates?.upper).toEqual({ min: 50, max: 100 });
    expect(features.speedGates?.mockNote).toContain('pitch');
  });

  it('keeps each speed mode server default inside its slider ranges', () => {
    // Server defaults: swing 30/130 mph, pitch 30/80 mph.
    expect(gateContains(getModeFeatures('swing-speed'), 30, 130)).toBe(true);
    expect(gateContains(getModeFeatures('pitch-speed'), 30, 80)).toBe(true);
  });

  it.each(['', 'slowpitch', 'SWING-SPEED', 'toString', '__proto__', 'constructor'])(
    'falls back to golf features for unknown mode %j',
    (mode) => {
      expect(getModeFeatures(mode)).toBe(getModeFeatures('rolling-buffer'));
    }
  );

  it('returns the same frozen object on every call', () => {
    for (const mode of ['rolling-buffer', 'mock', 'swing-speed', 'pitch-speed']) {
      expect(getModeFeatures(mode)).toBe(getModeFeatures(mode));
      expect(isDeepFrozen(getModeFeatures(mode))).toBe(true);
    }
  });
});
