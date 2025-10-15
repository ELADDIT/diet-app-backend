# Diet Mobile App

This Expo Router application consumes shared UI and theme packages from the Turborepo workspace. Tailwind tokens are provided by `@diet/theme` and utility classes are powered by NativeWind.

## Getting started

```bash
pnpm install
pnpm dev --filter mobile
```

### Launch targets

- **iOS Simulator**: `pnpm --filter mobile exec expo start --ios`
- **Android Emulator**: `pnpm --filter mobile exec expo start --android`
- **Web preview**: `pnpm --filter mobile exec expo start --web`

## Useful scripts

- `pnpm --filter mobile lint` – run ESLint over the Expo app
- `pnpm --filter mobile test` – execute Jest tests
- `pnpm --filter mobile build` – create a static web bundle via `expo export`
