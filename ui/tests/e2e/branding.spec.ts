import { test, type Page } from '@playwright/test';
import { expect, gotoApp, KIOSK_VIEWPORTS, resetSession, setClub, withControlSocket } from './helpers';

const THEME_STORAGE_KEY = 'openflight.theme';

async function dismissPicker(page: Page) {
  await page.getByRole('button', { name: 'Close Select club' }).click();
}

async function useTheme(page: Page, theme: 'dark' | 'light') {
  await page.addInitScript(
    ([key, value]) => {
      window.localStorage.setItem(key, value);
    },
    [THEME_STORAGE_KEY, theme] as const
  );
}

/** Footer controls must stay inside the viewport and must not overlap each other. */
async function footerLayoutProblems(page: Page): Promise<string[]> {
  return page.locator('.panel-footer').evaluate((footer) => {
    const problems: string[] = [];
    if (footer.scrollWidth > footer.clientWidth + 1) problems.push('footer scrolls horizontally');
    const controls = Array.from(footer.querySelectorAll('button')).filter((button) => button.offsetParent !== null);
    const boxes = controls.map((button) => ({
      name: button.getAttribute('aria-label') ?? button.textContent?.trim() ?? '?',
      rect: button.getBoundingClientRect(),
    }));
    for (const { name, rect } of boxes) {
      if (rect.left < 0 || rect.right > window.innerWidth + 1) problems.push(`${name} is outside the viewport`);
    }
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i].rect;
        const b = boxes[j].rect;
        const overlap = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const sameRow = Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top);
        if (sameRow && overlap > 1) problems.push(`${boxes[i].name} overlaps ${boxes[j].name}`);
      }
    }
    return problems;
  });
}

async function expectBrandLogo(page: Page, src: string) {
  const logo = page.locator('.panel-footer__menu .brand-logo');
  await expect(logo).toHaveAttribute('src', src);
  expect(await logo.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
}

test.beforeEach(async () => {
  await withControlSocket(async (socket) => {
    await resetSession(socket);
    await setClub(socket, 'driver');
  });
});

for (const viewport of KIOSK_VIEWPORTS) {
  test.describe(`branding at ${viewport.width}×${viewport.height}`, () => {
    test.use({ hasTouch: true, viewport });

    test('fits the OpenSwing wordmark in the footer and keeps every tab tappable', async ({ page }) => {
      await gotoApp(page);
      await dismissPicker(page);

      await expectBrandLogo(page, '/openswing-logo-on-dark-transparent.svg');
      expect(await footerLayoutProblems(page)).toEqual([]);

      for (const tab of ['Stats', 'Shots', 'Camera', 'Profiles', 'Debug', 'Live']) {
        await page.getByRole('button', { name: tab, exact: true }).tap();
        await expect(page.getByRole('button', { name: tab, exact: true })).toHaveAttribute('aria-pressed', 'true');
      }

      await page.getByRole('button', { name: 'Open menu' }).tap();
      await expect(page.getByText('OpenSwing · based on OpenFlight')).toBeVisible();
    });

    test('switches to the light wordmark in the light theme', async ({ page }) => {
      await useTheme(page, 'light');
      await gotoApp(page);
      await dismissPicker(page);

      await expectBrandLogo(page, '/openswing-logo-light.svg');
      expect(await footerLayoutProblems(page)).toEqual([]);
    });
  });
}

test('uses the OpenSwing icon in the browser tab', async ({ page }) => {
  await gotoApp(page);

  await expect(page).toHaveTitle('OpenSwing');
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/openswing-icon.svg');
});
