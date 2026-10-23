import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const css = readFileSync(fileURLToPath(new URL('../index.css', import.meta.url)), 'utf8');

type Rgb = [number, number, number];
interface Color {
  rgb: Rgb;
  alpha: number;
}

function themeTokens(theme: 'dark' | 'light'): Record<string, string> {
  const block = css.match(new RegExp(`\\[data-theme='${theme}'\\]\\s*\\{([^}]*)\\}`))?.[1];
  if (!block) throw new Error(`No [data-theme='${theme}'] block in index.css`);
  const tokens: Record<string, string> = {};
  for (const [, name, value] of block.matchAll(/(--color-[\w-]+):\s*([^;]+);/g)) {
    tokens[name] = value.trim();
  }
  return tokens;
}

function parseColor(value: string, tokens: Record<string, string>): Color {
  const reference = value.match(/^var\((--[\w-]+)\)$/);
  if (reference) return parseColor(tokens[reference[1]], tokens);
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = Number.parseInt(hex[1], 16);
    return { rgb: [(n >> 16) & 255, (n >> 8) & 255, n & 255], alpha: 1 };
  }
  const rgba = value.match(/^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/);
  if (rgba) return { rgb: [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])], alpha: Number(rgba[4]) };
  throw new Error(`Unsupported color: ${value}`);
}

function over(color: Color, background: Rgb): Rgb {
  return color.rgb.map((channel, i) => channel * color.alpha + background[i] * (1 - color.alpha)) as Rgb;
}

function luminance([r, g, b]: Rgb): number {
  const linear = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

function contrast(foreground: string, background: string, tokens: Record<string, string>): number {
  const bg = parseColor(tokens[background], tokens).rgb;
  const fg = over(parseColor(tokens[foreground], tokens), bg);
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

describe('theme tokens', () => {
  it('defines the same color tokens in both themes', () => {
    expect(Object.keys(themeTokens('light')).sort()).toEqual(Object.keys(themeTokens('dark')).sort());
  });

  // Kiosk targets for a bright gym on a 7-inch screen: 7:1 for primary text,
  // 4.5:1 for small or secondary text, 3:1 for the selected-tile border.
  describe.each(['dark', 'light'] as const)('%s theme contrast', (theme) => {
    const tokens = themeTokens(theme);

    it.each(['--color-bg', '--color-surface'])('keeps primary text at least 7:1 on %s', (background) => {
      expect(contrast('--color-text', background, tokens)).toBeGreaterThanOrEqual(7);
    });

    it.each([
      ['--color-text-muted', '--color-bg'],
      ['--color-text-muted', '--color-surface'],
      ['--color-text-faint', '--color-bg'],
      ['--color-text-faint', '--color-surface'],
      ['--color-accent', '--color-bg'],
      ['--color-accent', '--color-surface'],
    ])('keeps %s at least 4.5:1 on %s', (foreground, background) => {
      expect(contrast(foreground, background, tokens)).toBeGreaterThanOrEqual(4.5);
    });

    it('keeps text on accent fills at least 7:1', () => {
      expect(contrast('--color-accent-fg', '--color-accent-block', tokens)).toBeGreaterThanOrEqual(7);
    });

    it('keeps the selected border at least 3:1 against the background', () => {
      expect(contrast('--color-border-emphasis', '--color-bg', tokens)).toBeGreaterThanOrEqual(3);
    });
  });

  it('paints every dropdown option from the theme so native popups stay readable', () => {
    expect(css).toMatch(
      /select option \{\s*background-color: var\(--color-surface\);\s*color: var\(--color-text\);\s*\}/
    );
  });
});
