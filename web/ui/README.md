# XYolo UI

This frontend is the React + TypeScript console used by `xyolo web`.

## Layout model

The app shell follows a 1Panel-style left-right workspace:

- The left sidebar is the primary navigation for datasets, training, models, evaluation, and deploy
- The sidebar can be collapsed, and the preference is persisted in a browser cookie
- The right pane owns the active page content
- In the training section, **New / List / Template** stay as secondary tabs in the content header instead of top-level navigation

## Development

```bash
cd web/ui
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

The Vite dev server proxies `/api` and `/logs` to `http://127.0.0.1:8860`.

## Build

```bash
cd web/ui
corepack pnpm build
```

The production build writes static assets into `src/xyolo/static/` so they can be bundled into the Python package.
