import { test, type Page } from '@playwright/test';
import {
  expect,
  gotoApp,
  KIOSK_VIEWPORTS,
  liveMetricValueFontSizes,
  overflowingLiveMetricValues,
  PITCH_SOCKET_URL,
  resetSession,
  simulateShot,
  WIDEST_LIVE_METRIC_VALUE,
  withControlSocket,
} from './helpers';

/** Record whether any golf-only control appears at any point after navigation starts. */
async function watchForGolfControls(page: Page) {
  await page.addInitScript(() => {
    const flags = window as unknown as { sawGolfControls: boolean };
    flags.sawGolfControls = false;
    const check = () => {
      const header = document.querySelector('.panel-header__club')?.textContent ?? '';
      const golfChange = Array.from(document.querySelectorAll('button')).some((button) =>
        /^Change (club|implement)$/.test(button.textContent?.trim() ?? '')
      );
      if (document.querySelector('.picker-overlay') || golfChange || header === 'Driver') {
        flags.sawGolfControls = true;
      }
    };
    new MutationObserver(check).observe(document, { childList: true, subtree: true, characterData: true });
  });
}

async function simulatePitches(count: number) {
  await withControlSocket(async (socket) => {
    for (let index = 0; index < count; index += 1) {
      await simulateShot(socket);
    }
  }, PITCH_SOCKET_URL);
}

test.beforeEach(async () => {
  await withControlSocket(resetSession, PITCH_SOCKET_URL);
});

for (const viewport of KIOSK_VIEWPORTS) {
  test.describe(`pitch mode at ${viewport.width}×${viewport.height}`, () => {
    test.use({ hasTouch: true, viewport });

    test('never flashes golf controls while loading', async ({ page }) => {
      await watchForGolfControls(page);
      await gotoApp(page);

      await expect(page.locator('.panel-header__club')).toHaveText('Pitch Speed');
      await expect(page.getByRole('button', { name: 'Simulate pitch' })).toBeVisible();
      await expect(page.locator('.picker-overlay')).toHaveCount(0);
      expect(await page.evaluate(() => (window as unknown as { sawGolfControls: boolean }).sawGolfControls)).toBe(
        false
      );
    });

    test('fits four pitch tiles with one shared size', async ({ page }) => {
      await simulatePitches(3);
      await gotoApp(page);

      const tiles = page.locator('.live-panel__grid .metric-card');
      await expect(tiles).toHaveCount(4);
      await expect(page.locator('.live-panel__grid .metric-card__label')).toHaveText([
        'Last pitch',
        'Best',
        'Average',
        'Pitches',
      ]);
      await expect(tiles.nth(3).locator('.metric-card__value')).toHaveText('3');

      const sizes = await liveMetricValueFontSizes(page);
      expect(sizes.length).toBe(4);
      expect(new Set(sizes.map((size) => size.toFixed(2))).size).toBe(1);

      await page.locator('.live-panel__grid .metric-card__value').evaluateAll((values, widest) => {
        for (const value of values) {
          value.textContent = widest;
        }
      }, WIDEST_LIVE_METRIC_VALUE);
      await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())));

      expect(await overflowingLiveMetricValues(page)).toEqual([]);
    });

    test('shows pitch stats and pitch rows', async ({ page }) => {
      await simulatePitches(2);
      await gotoApp(page);

      await page.getByRole('button', { name: 'Stats' }).click();
      await expect(page.locator('.stats-panel__grid--of-4')).toBeVisible();
      await expect(page.getByText('Pitches', { exact: true })).toBeVisible();
      await expect(page.getByText('Avg ball')).toHaveCount(0);

      await page.getByRole('button', { name: 'Shots' }).click();
      await expect(page.locator('.shots-panel__row')).toHaveCount(2);
      await expect(page.locator('.shots-panel__columns')).toContainText('Speed');
      await expect(page.locator('.shots-panel__columns')).not.toContainText('Carry');
    });
  });
}
