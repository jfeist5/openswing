import { test, type Page } from '@playwright/test';
import { expect, gotoApp, resetSession, setClub, simulateShot, withControlSocket } from './helpers';

const THEME_STORAGE_KEY = 'openflight.theme';

async function useTheme(page: Page, theme: 'dark' | 'light') {
  await page.addInitScript(
    ([key, value]) => {
      window.localStorage.setItem(key, value);
    },
    [THEME_STORAGE_KEY, theme] as const
  );
}

/**
 * Native <select> popups paint options with the option's own colors. A
 * transparent option background falls back to the browser's white popup, so
 * inherited light text becomes unreadable; require an opaque background and
 * at least 4.5:1 contrast for every option.
 */
async function unreadableOptions(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const parse = (value: string) => {
      const match = value.match(/rgba?\(([^)]+)\)/);
      if (!match) return null;
      const [r, g, b, a = '1'] = match[1].split(/[,/\s]+/).filter(Boolean);
      return { rgb: [Number(r), Number(g), Number(b)], alpha: Number(a) };
    };
    const luminance = (rgb: number[]) => {
      const [r, g, b] = rgb.map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const problems: string[] = [];
    const selects = Array.from(document.querySelectorAll('select'));
    if (selects.length === 0) problems.push('no select found');
    for (const select of selects) {
      for (const option of Array.from(select.options)) {
        const style = getComputedStyle(option);
        const text = parse(style.color);
        const background = parse(style.backgroundColor);
        const label = `${select.className || select.name || 'select'} > "${option.textContent?.trim()}"`;
        if (!text || !background || background.alpha < 1) {
          problems.push(`${label}: background ${style.backgroundColor} is not opaque`);
          continue;
        }
        const [hi, lo] = [luminance(text.rgb), luminance(background.rgb)].sort((a, b) => b - a);
        const ratio = (hi + 0.05) / (lo + 0.05);
        if (ratio < 4.5) problems.push(`${label}: contrast ${ratio.toFixed(2)}`);
      }
    }
    return problems;
  });
}

test.beforeEach(async () => {
  await withControlSocket(async (socket) => {
    await resetSession(socket);
    await setClub(socket, 'driver');
    await simulateShot(socket);
  });
});

for (const theme of ['dark', 'light'] as const) {
  test.describe(`dropdowns in the ${theme} theme`, () => {
    test.use({ viewport: { width: 1024, height: 600 } });

    test('keeps language options readable in the menu', async ({ page }) => {
      await useTheme(page, theme);
      await gotoApp(page);
      await page.getByRole('button', { name: 'Close Select club' }).click();
      await page.getByRole('button', { name: 'Open menu' }).click();
      await expect(page.locator('.menu-sheet__select')).toBeVisible();

      expect(await unreadableOptions(page)).toEqual([]);
    });

    test('keeps comparator device options readable in the shot editor', async ({ page }) => {
      await useTheme(page, theme);
      await gotoApp(page);
      await page.getByRole('button', { name: 'Close Select club' }).click();
      await page.getByRole('button', { name: 'Shots' }).click();
      await page.locator('.shots-panel__row-main').first().click();
      await expect(page.locator('.shots-panel__field select')).toBeVisible();

      expect(await unreadableOptions(page)).toEqual([]);
    });
  });
}
