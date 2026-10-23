import { describe, expect, it } from 'vitest';
import type { Shot } from '../types/shot';
import type { ValidationEntry } from '../stores/useValidationStore';
import { buildValidationCsv, comparatorDifference, openflightSpeedMph } from './validationCsv';

function makeShot(overrides: Partial<Shot> = {}): Shot {
  return {
    ball_speed_mph: 150.25,
    club_speed_mph: 101.5,
    smash_factor: 1.48,
    estimated_carry_yards: 250,
    carry_range: [245, 255],
    club: 'driver',
    profile_name: 'James',
    timestamp: '2026-10-23T10:00:00Z',
    peak_magnitude: 42,
    launch_angle_vertical: 12,
    launch_angle_horizontal: 0,
    launch_angle_confidence: 0.8,
    angle_source: 'radar',
    club_angle_deg: null,
    club_path_deg: null,
    spin_axis_deg: null,
    spin_rpm: 2500,
    spin_confidence: 0.9,
    spin_quality: 'high',
    spin_source: 'measured',
    carry_spin_adjusted: null,
    mode: 'rolling-buffer',
    ...overrides,
  } as Shot;
}

const swingShot = makeShot({
  mode: 'swing-speed',
  club: 'Stack 60g',
  ball_speed_mph: 99,
  club_speed_mph: 104.3,
  training_implement_label: 'Stack 60g',
  swing_speed_reading_count: 7,
  swing_speed_trigger_mph: 41.2,
  swing_speed_duration_ms: 320,
});

const entry = (overrides: Partial<ValidationEntry> = {}): ValidationEntry => ({
  comparatorDevice: '',
  comparatorSpeed: '',
  notes: '',
  ...overrides,
});

describe('openflightSpeedMph', () => {
  it('uses ball speed for ball-strike shots and club speed for swing reps', () => {
    expect(openflightSpeedMph(makeShot())).toBe(150.25);
    expect(openflightSpeedMph(swingShot)).toBe(104.3);
  });
});

describe('comparatorDifference', () => {
  it('signs the difference against the comparator speed', () => {
    expect(comparatorDifference(swingShot, entry({ comparatorSpeed: '100' }))).toBeCloseTo(4.3);
  });

  it('returns null when no comparator speed was entered', () => {
    expect(comparatorDifference(swingShot, entry())).toBeNull();
    expect(comparatorDifference(swingShot, entry({ comparatorSpeed: 'fast' }))).toBeNull();
  });
});

describe('buildValidationCsv', () => {
  it('writes the header and one row per shot, with swing fields only on swing reps', () => {
    const csv = buildValidationCsv([makeShot(), swingShot], {
      [swingShot.timestamp]: entry({ comparatorDevice: 'Stack Radar', comparatorSpeed: '103.0', notes: 'ok' }),
    });

    expect(csv.split('\n')).toEqual([
      'shot_number,timestamp,profile,mode,implement,openflight_speed_mph,comparator_device,comparator_speed_mph,difference_mph,reading_count,trigger_speed_mph,duration_ms,peak_magnitude,notes',
      '1,2026-10-23T10:00:00Z,James,rolling-buffer,driver,150.3,Stack Radar,103.0,47.3,,,,42,ok',
      '2,2026-10-23T10:00:00Z,James,swing-speed,Stack 60g,104.3,Stack Radar,103.0,1.3,7,41.2,320,42,ok',
    ]);
  });

  it('quotes values containing commas, quotes, or newlines', () => {
    const csv = buildValidationCsv([makeShot({ profile_name: 'Smith, J' })], {
      [makeShot().timestamp]: entry({ notes: 'said "great"\nthen left' }),
    });

    expect(csv).toContain('"Smith, J"');
    expect(csv).toContain('"said ""great""\nthen left"');
  });

  it('exports pitch rows with their mode, label, peak speed, and stream fields', () => {
    const pitch = makeShot({
      mode: 'pitch-speed',
      club: 'Pitch',
      ball_speed_mph: 58.1,
      club_speed_mph: 58.1,
      training_implement_label: 'Pitch',
      swing_speed_reading_count: 11,
      swing_speed_trigger_mph: 41,
      swing_speed_duration_ms: 230,
    });

    expect(openflightSpeedMph(pitch)).toBe(58.1);
    expect(buildValidationCsv([pitch], {}).split('\n')[1]).toBe(
      '1,2026-10-23T10:00:00Z,James,pitch-speed,Pitch,58.1,,,,11,41,230,42,'
    );
  });
});
