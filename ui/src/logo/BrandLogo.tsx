import type { Theme } from '../theme/theme';
import { BRAND_LOGO_SRC } from './brandLogoSrc';

interface BrandLogoProps {
  theme: Theme;
}

export function BrandLogo({ theme }: BrandLogoProps) {
  return <img className="brand-logo" src={BRAND_LOGO_SRC[theme]} alt="" draggable={false} />;
}
