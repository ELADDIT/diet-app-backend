# Diet Web App

Next.js 14 is configured with the `@expo/next-adapter` so it can consume Expo SDK packages and share UI primitives with the mobile application. Tailwind consumes the shared theme tokens for neon-ready design primitives.

## Getting started

```bash
pnpm install
pnpm dev --filter web
```

### Launch commands

- **Development**: `pnpm --filter web dev`
- **Production build**: `pnpm --filter web build && pnpm --filter web start`
- **Static export**: `pnpm --filter web exec next export`

## Useful scripts

- `pnpm --filter web lint` – run ESLint with Next.js defaults
- `pnpm --filter web test` – execute Vitest suites
- `pnpm --filter web build` – compile the Next.js production bundle
