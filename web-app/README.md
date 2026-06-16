# Manager Web

Next.js presentation app for ARB manager workflows. Uses the EXL elite theme (light/dark), shadcn/ui, Tailwind CSS v4, and a thin route + `pages-components` page pattern.

## Run

```bash
npm install
npm run dev
```

Open [http://localhost:8811](http://localhost:8811).

## Build modes

| Command | Next.js build | Security scan (syft, grype, trivy) |
|---------|---------------|-------------------------------------|
| `npm run dev` | — (dev server) | No — fastest for debugging |
| `npm run build:fast` | Yes | No — quick compile check |
| `npm run build` | Yes | Yes — default production pipeline |
| `npm run build:prod` | Yes (`NODE_ENV=production`) | Yes |
| `npm run build:full` | Yes (manual full pipeline) | Yes |

Scan logs are written to **`manager-web/manager-web/<timestamp>/`** (folder name matches the project root folder). The directory is created automatically. Each run produces JSON/table reports plus per-tool log files and a `summary.log`.

Install scanners (once per machine):

- [Trivy](https://trivy.dev/latest/getting-started/installation/) — vulnerability, misconfiguration, and secret scanning
- [Syft](https://github.com/anchore/syft#installation) — SBOM extraction
- [Grype](https://github.com/anchore/grype#installation) — vulnerability matching

Skip scans when needed: `MANAGER_WEB_SKIP_SECURITY_SCAN=1 npm run build`

Run scans alone after a build: `npm run security:scan`

## Layout

- `/` — marketing home (matches aiassistant frontend landing page styling)
- `/pages/*` — dashboard shell with collapsible sidebar, header (theme toggle, avatar menu, logout)

## Structure

| Path | Role |
|------|------|
| `app/` | Next.js App Router routes (thin containers only) |
| `pages-components/` | One container component per page (`<name>/<name>-page.tsx`) |
| `components/layout/` | Sidebar, header, dashboard shell |
| `components/ui/` | shadcn/ui primitives |
| `lib/types/anyhow.ts` | Rust-style `AnyhowResult` / error types |
| `lib/types/option.ts` | Rust-style `Option<T>` helpers |

## Theme

Semantic CSS variables in `app/globals.css` — EXL orange primary, warm light surfaces, charcoal dark mode. Toggle via header appearance menu (`next-themes`).

## Build

```bash
npm run build        # production build + security scan
npm run build:fast   # compile only (no scan)
npm run build:full   # explicit full production pipeline
npm run start
```
