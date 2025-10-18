export const neonPalette = {
  pink: '#ff49db',
  blue: '#00f6ff',
  green: '#39ff14',
  purple: '#7d5bff',
  yellow: '#f7ff00'
} as const;

export const blurRadii = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '32px',
  xl: '48px'
} as const;

export const depthEffects = {
  soft: '0 10px 30px rgba(0, 246, 255, 0.15)',
  medium: '0 20px 45px rgba(61, 255, 184, 0.2)',
  intense: '0 30px 75px rgba(255, 73, 219, 0.35)'
} as const;

export const themeTokens = {
  colors: {
    background: '#030712',
    surface: '#0b1220',
    muted: '#6b7280',
    text: '#f8fafc',
    neon: neonPalette
  },
  blur: blurRadii,
  depth: depthEffects
};

export type ThemeTokens = typeof themeTokens;
