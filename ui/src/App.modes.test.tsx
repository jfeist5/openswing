import { renderToString } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { TriggerStatus } from './types/shot';
import { useDebugStore } from './stores/useDebugStore';
import { useSystemStore } from './stores/useSystemStore';

// zustand 5 renders getInitialState() during renderToString, so setState is
// invisible to SSR. Point these hooks at the live state for mode tests.
const { readLiveState } = vi.hoisted(() => ({
  readLiveState: <S,>(store: { getState: () => S }) =>
    Object.assign(<T,>(selector: (state: S) => T) => selector(store.getState()), store),
}));

vi.mock('./stores/useDebugStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./stores/useDebugStore')>();
  return { ...actual, useDebugStore: readLiveState(actual.useDebugStore) };
});

vi.mock('./stores/useSystemStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./stores/useSystemStore')>();
  return { ...actual, useSystemStore: readLiveState(actual.useSystemStore) };
});

function renderInMode(mode: string, mockMode = false): string {
  useDebugStore.setState({
    triggerStatus: { ...useDebugStore.getInitialState().triggerStatus, mode: mode as TriggerStatus['mode'] },
  });
  useSystemStore.setState({ mockMode, serverClub: null });
  return renderToString(<App />);
}

describe('App mode features', () => {
  afterEach(() => {
    useDebugStore.setState(useDebugStore.getInitialState());
    useSystemStore.setState(useSystemStore.getInitialState());
  });

  it('opens the club picker in golf rolling-buffer mode', () => {
    const html = renderInMode('rolling-buffer');

    expect(html).toContain('aria-label="Select club"');
    // Driver is the default and is pre-selected, and the picker is dismissible.
    expect(html).toMatch(/picker-overlay__option--selected[^>]*aria-pressed="true"[^>]*>DR</);
    expect(html).toContain('aria-label="Close Select club"');
    expect(html).not.toContain('picker-overlay--wide');
    expect(html).toContain('Change club');
    expect(html).toContain('panel-header__club">Driver<');
    expect(html).not.toContain('Simulate');
  });

  it('labels the mock golf simulate button as a shot', () => {
    const html = renderInMode('mock', true);

    expect(html).toContain('aria-label="Select club"');
    expect(html).toContain('Simulate shot');
  });

  it('opens the wide training-implement picker in swing-speed mode', () => {
    const html = renderInMode('swing-speed');

    expect(html).toContain('aria-label="Select implement"');
    expect(html).toContain('picker-overlay--wide');
    expect(html).toContain('Change implement');
    expect(html).not.toContain('aria-label="Select club"');
    expect(html).toContain('panel-header__club">Driver<');
  });

  it('labels the mock swing-speed simulate button as a swing', () => {
    const html = renderInMode('swing-speed', true);

    expect(html).toContain('Simulate swing');
    expect(html).not.toContain('Simulate shot');
  });

  it('hides every picker control in pitch-speed mode and labels the header', () => {
    const html = renderInMode('pitch-speed');

    expect(html).not.toContain('picker-overlay');
    expect(html).not.toContain('Change club');
    expect(html).not.toContain('Change implement');
    expect(html).toContain('panel-header__club">Pitch Speed<');
  });

  it('labels the mock pitch-speed simulate button as a pitch', () => {
    const html = renderInMode('pitch-speed', true);

    expect(html).toContain('Simulate pitch');
    expect(html).not.toContain('Simulate shot');
    expect(html).not.toContain('Simulate swing');
  });

  it('falls back to the golf club picker for a mode this UI does not know', () => {
    const html = renderInMode('slowpitch');

    expect(html).toContain('aria-label="Select club"');
    expect(html).toContain('Change club');
  });

  it('shows nothing mode-specific while connecting, even in mock mode', () => {
    const html = renderInMode('connecting', true);

    expect(html).not.toContain('picker-overlay');
    expect(html).not.toContain('Change club');
    expect(html).not.toContain('panel-header__club');
    expect(html).not.toContain('Simulate');
  });
});
