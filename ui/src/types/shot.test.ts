import { describe, expect, it } from 'vitest';
import type { Shot } from './shot';
import {
  computeSpeedStats,
  computeSwingSpeedStats,
  excludeShotsByProfile,
  filterShotsByProfile,
  filterSpeedShots,
  filterSwingSpeedShots,
  getShotKind,
  getSpeedSessionKind,
  getSwingSpeedMph,
  isPitchSpeedShot,
  isSwingSpeedShot,
} from './shot';

describe('filterShotsByProfile', () => {
  const shotWith = (profileId: string | undefined): Shot => ({ profile_id: profileId, ball_speed_mph: 100 }) as Shot;

  it('keeps only shots stamped with the given profile id', () => {
    const shots = [shotWith('aaa'), shotWith('bbb'), shotWith('aaa')];

    expect(filterShotsByProfile(shots, 'aaa')).toHaveLength(2);
  });

  it('matches exactly, without folding case', () => {
    const shots = [shotWith('AAA'), shotWith('aaa')];

    expect(filterShotsByProfile(shots, 'aaa')).toEqual([shots[1]]);
  });

  it('excludes unstamped shots from every profile', () => {
    const shots = [shotWith(undefined), shotWith('')];

    expect(filterShotsByProfile(shots, 'aaa')).toEqual([]);
    expect(filterShotsByProfile(shots, 'bbb')).toEqual([]);
  });

  it('returns nothing for a blank profile id', () => {
    const shots = [shotWith('aaa'), shotWith(undefined)];

    expect(filterShotsByProfile(shots, '')).toEqual([]);
  });
});

describe('excludeShotsByProfile', () => {
  const shotWith = (profileId: string | undefined): Shot => ({ profile_id: profileId, ball_speed_mph: 100 }) as Shot;

  it('drops only the given profile and keeps unstamped shots', () => {
    const shots = [shotWith('aaa'), shotWith('bbb'), shotWith(undefined)];

    expect(excludeShotsByProfile(shots, 'aaa')).toEqual([shots[1], shots[2]]);
  });

  it('excludes nothing for a blank profile id', () => {
    const shots = [shotWith('aaa'), shotWith('bbb')];

    expect(excludeShotsByProfile(shots, '')).toEqual(shots);
  });
});

function speedShot(overrides: Partial<Shot> = {}): Shot {
  return {
    ball_speed_mph: 100,
    club_speed_mph: 100,
    smash_factor: null,
    estimated_carry_yards: 0,
    carry_range: [0, 0],
    club: 'Driver',
    profile_id: 'p1',
    timestamp: '2026-10-23T10:00:00Z',
    peak_magnitude: null,
    launch_angle_vertical: null,
    launch_angle_horizontal: null,
    launch_angle_confidence: null,
    angle_source: null,
    club_angle_deg: null,
    club_path_deg: null,
    spin_axis_deg: null,
    spin_rpm: null,
    spin_confidence: null,
    spin_quality: null,
    spin_source: null,
    carry_spin_adjusted: null,
    mode: 'swing-speed',
    ...overrides,
  } as Shot;
}

describe('isSwingSpeedShot', () => {
  it('recognizes swing-speed mode and the legacy Swing Speed club', () => {
    expect(isSwingSpeedShot(speedShot())).toBe(true);
    expect(isSwingSpeedShot(speedShot({ mode: undefined, club: 'Swing Speed' }))).toBe(true);
  });

  it('rejects ball-strike shots, pitches, and null', () => {
    expect(isSwingSpeedShot(speedShot({ mode: 'rolling-buffer', club: 'driver' }))).toBe(false);
    expect(isSwingSpeedShot(speedShot({ mode: 'mock', club: 'driver' }))).toBe(false);
    expect(isSwingSpeedShot(speedShot({ mode: 'pitch-speed', club: 'Pitch' }))).toBe(false);
    expect(isSwingSpeedShot(null)).toBe(false);
  });
});

describe('getSwingSpeedMph', () => {
  it('prefers the club speed and falls back to ball speed', () => {
    expect(getSwingSpeedMph(speedShot({ club_speed_mph: 97.5, ball_speed_mph: 10 }))).toBe(97.5);
    expect(getSwingSpeedMph(speedShot({ club_speed_mph: null, ball_speed_mph: 88 }))).toBe(88);
  });
});

describe('filterSwingSpeedShots', () => {
  const shots = [
    speedShot({
      timestamp: 't1',
      club: 'Stack 60g',
      training_implement: 'stack-60g',
      training_implement_label: 'Stack 60g',
    }),
    speedShot({ timestamp: 't2', training_implement: 'driver', training_implement_label: 'Driver' }),
    speedShot({ timestamp: 't3', profile_id: 'p2', training_implement: 'driver' }),
    speedShot({ timestamp: 't4', mode: 'rolling-buffer', club: 'driver' }),
  ];
  const stamps = (list: Shot[]) => list.map((shot) => shot.timestamp);

  it('keeps only swing-speed shots, across profiles when unscoped', () => {
    expect(stamps(filterSwingSpeedShots(shots))).toEqual(['t1', 't2', 't3']);
  });

  it('scopes to a profile', () => {
    expect(stamps(filterSwingSpeedShots(shots, { profileId: 'p1' }))).toEqual(['t1', 't2']);
  });

  it('matches an implement by id, label, or club, ignoring case and spaces', () => {
    expect(stamps(filterSwingSpeedShots(shots, { trainingImplement: 'stack-60g' }))).toEqual(['t1']);
    expect(stamps(filterSwingSpeedShots(shots, { trainingImplement: '  STACK 60G ' }))).toEqual(['t1']);
    expect(stamps(filterSwingSpeedShots(shots, { profileId: 'p1', trainingImplement: 'Driver' }))).toEqual(['t2']);
  });

  it('filters by club when no implement is given', () => {
    expect(stamps(filterSwingSpeedShots(shots, { club: 'driver' }))).toEqual(['t2', 't3']);
    expect(stamps(filterSwingSpeedShots(shots, { club: 'Stack 60g' }))).toEqual(['t1']);
  });
});

describe('computeSwingSpeedStats', () => {
  it('returns zeros when there are no swing-speed shots', () => {
    expect(computeSwingSpeedStats([speedShot({ mode: 'rolling-buffer', club: 'driver' })])).toEqual({
      count: 0,
      last_speed_mph: 0,
      best_speed_mph: 0,
      avg_speed_mph: 0,
    });
  });

  it('summarizes count, last, best, and average in session order', () => {
    const shots = [
      speedShot({ club_speed_mph: 95 }),
      speedShot({ club_speed_mph: 105 }),
      speedShot({ club_speed_mph: 98 }),
      speedShot({ mode: 'pitch-speed', club: 'Pitch', club_speed_mph: 60 }),
    ];

    expect(computeSwingSpeedStats(shots)).toEqual({
      count: 3,
      last_speed_mph: 98,
      best_speed_mph: 105,
      avg_speed_mph: 99.33333333333333,
    });
  });
});

describe('getShotKind', () => {
  it('classifies each server mode', () => {
    expect(getShotKind(speedShot({ mode: 'pitch-speed', club: 'Pitch' }))).toBe('pitch-speed');
    expect(getShotKind(speedShot({ mode: 'swing-speed' }))).toBe('swing-speed');
    expect(getShotKind(speedShot({ mode: 'rolling-buffer', club: 'driver' }))).toBe('ball-strike');
    expect(getShotKind(speedShot({ mode: 'mock', club: 'driver' }))).toBe('ball-strike');
  });

  it('keeps the legacy Swing Speed club and treats a missing mode as a ball strike', () => {
    expect(getShotKind(speedShot({ mode: undefined, club: 'Swing Speed' }))).toBe('swing-speed');
    expect(getShotKind(speedShot({ mode: undefined, club: 'driver' }))).toBe('ball-strike');
  });

  it('lets the pitch mode win over a stray Swing Speed club label', () => {
    expect(getShotKind(speedShot({ mode: 'pitch-speed', club: 'Swing Speed' }))).toBe('pitch-speed');
  });
});

describe('isPitchSpeedShot', () => {
  it('accepts only pitch-speed shots', () => {
    expect(isPitchSpeedShot(speedShot({ mode: 'pitch-speed', club: 'Pitch' }))).toBe(true);
    expect(isPitchSpeedShot(speedShot())).toBe(false);
    expect(isPitchSpeedShot(null)).toBe(false);
  });
});

describe('pitch speed stats', () => {
  const pitch = (speed: number, overrides: Partial<Shot> = {}) =>
    speedShot({ mode: 'pitch-speed', club: 'Pitch', club_speed_mph: speed, ball_speed_mph: speed, ...overrides });
  const shots = [pitch(55), speedShot({ club_speed_mph: 110 }), pitch(61), pitch(58, { profile_id: 'p2' })];

  it('filters to pitches only, optionally per profile', () => {
    expect(filterSpeedShots(shots, 'pitch-speed').map(getSwingSpeedMph)).toEqual([55, 61, 58]);
    expect(filterSpeedShots(shots, 'pitch-speed', { profileId: 'p1' }).map(getSwingSpeedMph)).toEqual([55, 61]);
  });

  it('summarizes pitches without counting swings', () => {
    expect(computeSpeedStats(shots, 'pitch-speed', { profileId: 'p1' })).toEqual({
      count: 2,
      last_speed_mph: 61,
      best_speed_mph: 61,
      avg_speed_mph: 58,
    });
  });
});

describe('getSpeedSessionKind', () => {
  const pitch = speedShot({ mode: 'pitch-speed', club: 'Pitch' });
  const swing = speedShot();
  const strike = speedShot({ mode: 'rolling-buffer', club: 'driver' });

  it('returns the shared speed-only kind', () => {
    expect(getSpeedSessionKind([pitch, pitch])).toBe('pitch-speed');
    expect(getSpeedSessionKind([swing])).toBe('swing-speed');
  });

  it('returns null for empty, ball-strike, or mixed sessions', () => {
    expect(getSpeedSessionKind([])).toBeNull();
    expect(getSpeedSessionKind([strike])).toBeNull();
    expect(getSpeedSessionKind([pitch, swing])).toBeNull();
    expect(getSpeedSessionKind([pitch, strike])).toBeNull();
  });
});
