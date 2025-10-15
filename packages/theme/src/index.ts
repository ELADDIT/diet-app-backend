import { blurRadii, depthEffects, neonPalette, themeTokens } from './tokens';

export * from './tokens';

export const tailwindTheme = {
  colors: {
    background: themeTokens.colors.background,
    surface: themeTokens.colors.surface,
    muted: themeTokens.colors.muted,
    text: themeTokens.colors.text,
    ...Object.fromEntries(
      Object.entries(neonPalette).map(([key, value]) => [`neon-${key}`, value])
    )
  },
  extend: {
    blur: blurRadii,
    boxShadow: {
      ...Object.fromEntries(
        Object.entries(depthEffects).map(([key, value]) => [`neon-${key}`, value])
      )
    }
  }
};
