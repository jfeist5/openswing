import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { catalogs } from './i18n';

const uiFile = (path: string) => fileURLToPath(new URL(`../${path}`, import.meta.url));
const read = (path: string) => readFileSync(uiFile(path), 'utf8');

const OLD_ACCENTS = ['#ffd400', '#ffbe1b', '#e5be3f'];
const OLD_ACCENT_RGB = /\b(255[ ,]+212[ ,]+0|255[ ,]+190[ ,]+27|229[ ,]+190[ ,]+63)\b/;

describe('OpenSwing branding', () => {
  it('ships the logo and icon files the UI references', () => {
    for (const file of [
      'openswing-logo-on-dark-transparent.svg',
      'openswing-logo-light.svg',
      'openswing-logo-dark.svg',
      'openswing-icon.svg',
    ]) {
      expect(existsSync(uiFile(`public/${file}`)), file).toBe(true);
    }
  });

  it('uses the OpenSwing icon and title in the app page', () => {
    const html = read('index.html');

    expect(html).toContain('<link rel="icon" type="image/svg+xml" href="/openswing-icon.svg" />');
    expect(html).toContain('<title>OpenSwing</title>');
    expect(html).not.toContain('vite.svg');
  });

  it('brands the startup splash and drops the old accent', () => {
    const splash = read('public/startup-splash.html');

    expect(splash).toContain('src="openswing-logo-on-dark-transparent.svg"');
    expect(splash).toContain('alt="OpenSwing"');
    expect(splash).toContain('<title>Starting OpenSwing</title>');
    expect(splash.toLowerCase()).toContain('#cfc18c');
    for (const accent of OLD_ACCENTS) {
      expect(splash.toLowerCase()).not.toContain(accent);
    }
  });

  it('removes the old accent colors from the theme', () => {
    const css = read('src/index.css').toLowerCase();

    for (const accent of OLD_ACCENTS) {
      expect(css).not.toContain(accent);
    }
    expect(css).toContain('#cfc18c');
  });

  it.each(Object.entries(catalogs))('names the product OpenSwing in %s, crediting OpenFlight once', (_, messages) => {
    const mentions = Object.entries(messages).filter(([, text]) => text.includes('OpenFlight'));

    expect(mentions.map(([key]) => key)).toEqual(['menu.credit']);
    expect(messages['menu.credit']).toContain('OpenSwing');
    expect(messages['shutdown.confirm']).toContain('OpenSwing');
    expect(messages['display.eyebrow']).toContain('OpenSwing');
  });

  it('keeps the old accent out of every stylesheet except the Launch Daddy easter egg', () => {
    const stylesheets = readdirSync(uiFile('src'), { recursive: true, encoding: 'utf8' })
      .filter((path) => path.endsWith('.css') && !path.includes('LaunchDaddy'))
      .map((path) => `src/${path}`);

    expect(stylesheets.length).toBeGreaterThan(10);
    for (const path of [...stylesheets, 'public/startup-splash.html']) {
      const text = read(path).toLowerCase();
      expect(
        OLD_ACCENTS.filter((accent) => text.includes(accent)),
        path
      ).toEqual([]);
      expect(text, path).not.toMatch(OLD_ACCENT_RGB);
    }
  });

  it('marks the selected tile with the contrast-checked emphasis color, not the gold fill', () => {
    const css = read('src/components/ui/MetricCard.css');

    expect(css).toMatch(/\.metric-card--selected \{\s*box-shadow: inset 5px 0 0 var\(--color-border-emphasis\);/);
  });
});
