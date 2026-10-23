import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { BrandLogo } from './BrandLogo';
import { BRAND_LOGO_SRC } from './brandLogoSrc';

describe('BrandLogo', () => {
  it('uses the transparent on-dark wordmark in the dark theme', () => {
    const html = renderToString(<BrandLogo theme="dark" />);

    expect(html).toContain('src="/openswing-logo-on-dark-transparent.svg"');
  });

  it('uses the light wordmark, whose white box blends into the light background', () => {
    const html = renderToString(<BrandLogo theme="light" />);

    expect(html).toContain('src="/openswing-logo-light.svg"');
  });

  it('is decorative so the enclosing button keeps its own label', () => {
    expect(renderToString(<BrandLogo theme="dark" />)).toContain('alt=""');
  });

  it('maps every theme to a shipped logo', () => {
    expect(BRAND_LOGO_SRC).toEqual({
      dark: '/openswing-logo-on-dark-transparent.svg',
      light: '/openswing-logo-light.svg',
    });
  });
});
