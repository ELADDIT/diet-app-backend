import type { Config } from 'tailwindcss';
import { tailwindTheme } from '@diet/theme';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', '../../packages/ui/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: tailwindTheme.colors,
      blur: tailwindTheme.extend.blur,
      boxShadow: tailwindTheme.extend.boxShadow
    }
  },
  plugins: []
};

export default config;
