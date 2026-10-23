import type { Theme } from '../theme/theme';

/** Light theme uses the boxed light wordmark; its white box blends into the white background. */
export const BRAND_LOGO_SRC: Readonly<Record<Theme, string>> = Object.freeze({
  dark: '/openswing-logo-on-dark-transparent.svg',
  light: '/openswing-logo-light.svg',
});
