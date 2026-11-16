import { describe, expect, it } from 'vitest';
import type { Shot } from '../types/shot';
import { comparatorDevicesFor, GOLF_COMPARATOR_DEVICES, PITCH_COMPARATOR_DEVICES } from './comparatorDevices';

function shot(overrides: Partial<Shot> = {}): Shot {
  return { mode: 'rolling-buffer', club: 'driver', ...overrides } as Shot;
}

describe('comparatorDevicesFor', () => {
  it('keeps the golf comparator list for ball strikes and swing reps', () => {
    expect(GOLF_COMPARATOR_DEVICES).toEqual(['Stack Radar', 'PRGR', 'TrackMan', 'Full Swing', 'Other']);
    expect(comparatorDevicesFor(shot())).toEqual(GOLF_COMPARATOR_DEVICES);
    expect(comparatorDevicesFor(shot({ mode: 'swing-speed' }))).toEqual(GOLF_COMPARATOR_DEVICES);
  });

  it('offers the facility radar guns for pitches', () => {
    expect(PITCH_COMPARATOR_DEVICES).toEqual(['Pocket Radar', 'Stalker', 'Other']);
    expect(comparatorDevicesFor(shot({ mode: 'pitch-speed', club: 'Pitch' }))).toEqual(PITCH_COMPARATOR_DEVICES);
  });

  it('keeps a saved device that is not in the list so it still shows as selected', () => {
    expect(comparatorDevicesFor(shot({ mode: 'pitch-speed' }), 'TrackMan')).toEqual([
      ...PITCH_COMPARATOR_DEVICES,
      'TrackMan',
    ]);
  });

  it('does not duplicate a saved device that is already listed or empty', () => {
    expect(comparatorDevicesFor(shot({ mode: 'pitch-speed' }), 'Stalker')).toEqual(PITCH_COMPARATOR_DEVICES);
    expect(comparatorDevicesFor(shot(), '')).toEqual(GOLF_COMPARATOR_DEVICES);
  });

  it('returns a fresh array so callers cannot change the shared lists', () => {
    const devices = comparatorDevicesFor(shot());
    devices.push('Mutated');

    expect(GOLF_COMPARATOR_DEVICES).not.toContain('Mutated');
  });
});
