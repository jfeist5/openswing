import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { TriggerStatus } from '../types/shot';
import type { RadarConfig } from '../types/socket';
import { RadarTuning } from './DebugPanel';

const RADAR_CONFIG: RadarConfig = { min_speed: 30, max_speed: 130, min_magnitude: 0, transmit_power: 0 };

interface RenderedSlider {
  label: string;
  min: number;
  max: number;
  disabled: boolean;
}

function renderTuning(mode: string, mockMode: boolean, radarConfig: RadarConfig = RADAR_CONFIG): string {
  return renderToString(
    <RadarTuning
      mode={mode as TriggerStatus['mode']}
      radarConfig={radarConfig}
      mockMode={mockMode}
      onUpdateConfig={() => {}}
    />
  );
}

function sliders(html: string): RenderedSlider[] {
  const pattern =
    /slider-control__label">([^<]+)<[\s\S]*?<input type="range"[^>]*min="(-?\d+)" max="(-?\d+)"([^>]*)\/>/g;
  return [...html.matchAll(pattern)].map(([, label, min, max, rest]) => ({
    label,
    min: Number(min),
    max: Number(max),
    disabled: rest.includes('disabled'),
  }));
}

describe('RadarTuning', () => {
  it('shows lower/upper speed gates for swing speed', () => {
    const html = renderTuning('swing-speed', false);

    expect(sliders(html)).toEqual([
      { label: 'Lower Speed', min: 30, max: 100, disabled: false },
      { label: 'Upper Speed', min: 90, max: 170, disabled: false },
      { label: 'TX Power', min: 0, max: 7, disabled: false },
    ]);
    expect(html).toContain('upper speed rejects implausible high swing-speed outliers');
    expect(html).not.toContain('debug-panel__mock-warning');
  });

  it('keeps swing speed gates live in mock mode with a simulated-reps note', () => {
    const html = renderTuning('swing-speed', true);

    expect(sliders(html)).toEqual([
      { label: 'Lower Speed', min: 30, max: 100, disabled: false },
      { label: 'Upper Speed', min: 90, max: 170, disabled: false },
      { label: 'TX Power', min: 0, max: 7, disabled: true },
    ]);
    expect(html).toContain('Mock swing speed sliders shape simulated reps only');
    expect(html).not.toContain('Radar tuning disabled in mock mode');
  });

  it('shows min speed and magnitude filters for the golf launch monitor', () => {
    const html = renderTuning('rolling-buffer', false);

    expect(sliders(html)).toEqual([
      { label: 'Min Speed', min: 0, max: 50, disabled: false },
      { label: 'Min Magnitude', min: 0, max: 2000, disabled: false },
      { label: 'TX Power', min: 0, max: 7, disabled: false },
    ]);
    expect(html).toContain('TX Power: 0 = max range, 7 = min range');
  });

  it('disables golf tuning in mock mode', () => {
    const html = renderTuning('mock', true);

    expect(sliders(html).every((slider) => slider.disabled)).toBe(true);
    expect(html).toContain('Radar tuning disabled in mock mode');
  });

  it('shows fastpitch lower/upper speed gates for pitch speed', () => {
    const html = renderTuning('pitch-speed', false, { ...RADAR_CONFIG, max_speed: 80 });

    expect(sliders(html)).toEqual([
      { label: 'Lower Speed', min: 15, max: 60, disabled: false },
      { label: 'Upper Speed', min: 50, max: 100, disabled: false },
      { label: 'TX Power', min: 0, max: 7, disabled: false },
    ]);
    expect(html).toContain('upper speed rejects implausible high pitch-speed outliers');
    expect(html).not.toContain('swing');
  });

  it('keeps pitch speed gates live in mock mode with a simulated-pitches note', () => {
    const html = renderTuning('pitch-speed', true);

    expect(
      sliders(html)
        .slice(0, 2)
        .every((slider) => !slider.disabled)
    ).toBe(true);
    expect(html).toContain('Mock pitch speed sliders shape simulated pitches only');
    expect(html).not.toContain('Radar tuning disabled in mock mode');
  });

  it('falls back to the golf filters for an unknown mode', () => {
    const html = renderTuning('slowpitch', false);

    expect(sliders(html).map((slider) => slider.label)).toEqual(['Min Speed', 'Min Magnitude', 'TX Power']);
  });
});
