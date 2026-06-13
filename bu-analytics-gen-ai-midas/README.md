<!--
  Repository root README.md — EXLdecision landing page.
  This is the page Git hosts (GitHub / Gitea / GitLab) render at the
  repository home. Keep the focus on EXLdecision itself; the long-form
  MIDAS overview is preserved at ./README.midas.md.

  When editing:
  - Keep the Getting started one-liner in a fenced code block so the
    Git host renders its native copy icon.
  - The launcher script lives at deploy/scripts/exldecision-launch.sh.
-->

## Interactive architecture diagrams (HTML)

This repository ships a **static HTML diagram site** under [`docs/html_diagram/`](docs/html_diagram/) so architects and developers can explore EXLDecision **current-state** and **future-state** backend views in a browser **without a server**. Open any page with `file://` from your checkout or via your editor’s preview.

**What you get**

- **Future-state Developer Architecture Diagram** — primary diagram: services, fabrics, hover tooltips, scenario flows, and a detail panel linked to the requirements and decisions registers.
- **Current Architecture (simplified)** — [`docs/html_diagram/current/index.html`](docs/html_diagram/current/index.html): high-level monolith view and motivation for the microservice target.
- **Future-state registers** — [`docs/html_diagram/future/requirements/index.html`](docs/html_diagram/future/requirements/index.html) (REQ traceability) and [`docs/html_diagram/future/decisions/index.html`](docs/html_diagram/future/decisions/index.html) (ADRs), aligned with the Developer diagram.
- **Final-state tree** — [`docs/html_diagram/final/`](docs/html_diagram/final/) holds the **stable reference** copies of the same diagram layouts (system layer, SVG, classic, layered, microservice, developer, requirements). The **`future/`** tree is the **editable fork** for planned diagram changes.

**Automatic landing on the Future Developer diagram**

These entry URLs **immediately redirect** to [`docs/html_diagram/future/developer/index.html`](docs/html_diagram/future/developer/index.html):

| Entry file | Role |
|------------|------|
| [`docs/html_diagram/index.html`](docs/html_diagram/index.html) | Folder root |
| [`docs/html_diagram/start-here/index.html`](docs/html_diagram/start-here/index.html) | Documented “start here” path |
| [`docs/html_diagram/developer/index.html`](docs/html_diagram/developer/index.html) | Legacy `developer/` shortcut |

**Navigation**

Diagram pages use a compact sidebar: **Start Here** (overview redirect), **Current state**, and **Future state** links to the Developer diagram, Requirements, and Decisions. Pages that are not one of those three also show **This diagram** so you know which view you are on.

**Other Future-state views** (same folder family): [system layer](docs/html_diagram/future/index.html), [SVG](docs/html_diagram/future/architecture.html), [classic](docs/html_diagram/future/classic/index.html), [layered](docs/html_diagram/future/layered/index.html), [microservice](docs/html_diagram/future/microservice/index.html).

---

<div align="center">

<img src="docs/images/exl-service-logo.png" alt="EXLService" width="200" />

<br/><br/>

<img src="docs/images/atlas-banner.svg" alt="EXLdecision" width="100%" />

<br/>

# EXLdecision

**A guided, browser-based map of the EXLdecision solution.**
Land on the repo, paste one command, and start exploring the architecture, deploy path, activity, glossary, and code flow — without grep, without tribal knowledge.

<br/>

<a href="#getting-started"><img alt="Get started" src="https://img.shields.io/badge/%E2%96%B6%20Get%20started-1f1f3b?style=for-the-badge&labelColor=4f46e5&color=1f1f3b"/></a>
&nbsp;
<a href="./atlas/"><img alt="Source code" src="https://img.shields.io/badge/Source%20code-atlas%2F-0f172a?style=for-the-badge&logo=github&logoColor=white"/></a>
&nbsp;
<a href="./atlas/agent/README.md"><img alt="Agent docs" src="https://img.shields.io/badge/AI%20agent%20notes-agent%2FREADME.md-0f172a?style=for-the-badge"/></a>

<br/><br/>

<sup>Stack: Next.js 15 · React 19 · TypeScript (strict) · Tailwind v4 · shadcn-style primitives · Zod · TanStack Query · ky</sup>

</div>

---

## Getting started

EXLdecision ships with a **companion app** that walks you through the architecture, deploy path, recent activity, glossary, and an interactive code-flow analyzer for this repository. The companion app runs entirely on your **MacBook** — no servers, no shared environments — and opens in your default browser.

### macOS only

The launcher requires a MacBook (`darwin`). If you run it on Linux or Windows it will detect that and exit with a friendly message before doing anything else.

### One-line bootstrap

Click the copy icon on the code block below, then paste the command into your **macOS Terminal** and press Return:

```bash
bash <(curl -fsSL https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-analytics-gen-ai-midas/raw/branch/main/deploy/scripts/exldecision-launch.sh)
```

### What this does

1. **Downloads** [`deploy/scripts/exldecision-launch.sh`](deploy/scripts/exldecision-launch.sh) from this repo and runs it.
2. **Verifies** you are on macOS and that `git`, `node` (≥ 20), and `npm` are installed. If anything is missing it tells you exactly what to install and stops.
3. **Wipes** any previous checkout at `/tmp/exldecision-atlas` and **clones** this repository (`https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-analytics-gen-ai-midas.git`) into that folder.
4. **Installs** the companion app's dependencies under `/tmp/exldecision-atlas/atlas/` and starts the Next.js dev server.
5. **Captures** the `http://localhost:<port>` URL the dev server prints and **opens it in your default browser**, landing you on the EXLdecision Home page.

To stop the companion app, press `Ctrl-C` in the terminal where you ran the command.

### What you'll see

| Page | What it shows |
|---|---|
| Home | EXLdecision overview and quick links |
| Activity | Latest commits across the configured Git project, plus CI traffic-lights from a JSON build-status feed |
| Solution map | Layered architecture: Presentation → Orchestration → AI/ML → Data → Platform → CI/CD |
| Deploy path | The exact path a change takes to `dev` / `uat` / `prod` via the pipeline-first deploy flow |
| Code flow | Auto-clones this repo into a temp subfolder, then runs the embedded code-flow analyzer against it (asks before re-cloning on revisit) |
| Glossary | Canonical EXLdecision terms |
| Settings | Theme, Git project, optional PAT, build-status feed URL |

> The companion app is **client-side and local-only**: nothing leaves your machine. Settings live in `localStorage` behind an explicit consent prompt and can be wiped with a single **Start fresh** click.

---

For the long-form MIDAS solution overview (architecture deep-dive, document index, changelog, glossary), see [`README.midas.md`](README.midas.md).
