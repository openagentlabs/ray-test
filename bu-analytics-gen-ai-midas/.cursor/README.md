<!--
  MIDAS — Cursor workspace (.cursor)
  Companion to repository README.md Section 2.4 (see ../README.md).
  Follow .cursor/rules/doc.mdc when editing documentation that references deploy paths.
-->

<div align="center">

  # Cursor workspace (`.cursor`)

  **IDE rules, skills, scripts, and tooling for MIDAS — not the Jenkins pipeline tree.**

  <br/>

  ![Scope](https://img.shields.io/badge/scope-laptop%20%2F%20agent-blue?style=flat-square)
  ![Region](https://img.shields.io/badge/AWS-us--east--1-orange?style=flat-square)
  ![Pipeline](https://img.shields.io/badge/deploy-via-Jenkins-yellow?style=flat-square)

</div>

---

<div align="center">

| Field | Value |
|---|---|
| **Document** | `.cursor` folder guide |
| **Version** | `1.1.0` |
| **Status** | Active |
| **Date** | 2026-04-18 |
| **Repository** | `bu-analytics-gen-ai-midas` |
| **Master index** | [`README.midas.md`](../README.midas.md) (long-form MIDAS overview; the root `README.md` is the Atlas landing page) |

</div>

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. New to MIDAS Cursor tooling?](#2-new-to-midas-cursor-tooling)
- [3. JET — one keyword for natural language](#3-jet--one-keyword-for-natural-language)
- [4. Where to add or change things](#4-where-to-add-or-change-things)
- [5. Top-level folders](#5-top-level-folders)
- [6. Related paths](#6-related-paths)
- [7. Conventions](#7-conventions)
- [8. Restructure and cleanup plan](#8-restructure-and-cleanup-plan)

---

## 1. Overview

The **`.cursor/`** directory holds **Cursor IDE** and **agent** configuration for this repository: persistent rules, reusable skills, local helper scripts, and small tools that **skills** can invoke. It complements **`deploy/`** (Terraform, Helm, Jenkinsfiles) and **`docs/`** (human-facing solution documentation).

| Principle | Notes |
|---|---|
| **Pipeline-first** | Shared environment changes still go through Jenkins — see [`.cursor/rules/jenkins.mdc`](rules/jenkins.mdc) and [`README.midas.md`](../README.midas.md) §3.3. |
| **Read-only by default** | Many scripts only plan, validate, or query AWS/Jenkins; destructive flags require explicit operator consent. |
| **Single source for agent rules** | Files under **`rules/`** encode MIDAS architecture, constants, and tool usage expectations. |

---

## 2. New to MIDAS Cursor tooling?

These steps explain **what this folder is for** and **why** it exists beside `deploy/` and `docs/`.

1. **Understand non-negotiables** — Read [`.cursor/rules/architecture.mdc`](rules/architecture.mdc) (private-by-default, single region) and [`.cursor/rules/jenkins.mdc`](rules/jenkins.mdc) (shared environments are changed **only** via the Jenkins pipeline, not laptop `terraform apply` / `helm upgrade`).
2. **Use exact platform IDs when writing commands or IaC** — [`.cursor/rules/solution_const.mdc`](rules/solution_const.mdc) (VPC, jumpbox, Transit Gateway, region).
3. **Prefer skills over improvisation** — Skills under [`skills/`](skills/) encode approved workflows (Jenkins, git, Terraform validation, connectivity checks). The AI should **read the matching skill** before running helpers in `scripts/` or `tools/`.
4. **Run helpers, do not fork policy** — Scripts print `--help`; mutating flags require explicit human consent as described in each skill.
5. **Solution docs live in `docs/`** — This README is for **Cursor agents and IDE automation**; the solution index and getting-started guide are [`README.midas.md`](../README.midas.md) at the repository root. The repo's default landing page (root `README.md`) is the Atlas SPA showcase.

---

## 3. JET — one keyword for natural language

**JET** is a team **keyword prefix** (`jet`, case-insensitive) for plain-language requests so operators and the AI share one habit: *prefix + intent*. It does not start a separate binary; it tells the agent to route intent using [`.cursor/JET.md`](JET.md).

Examples:

- `jet deploy to dev and watch the pipeline`
- `jet validate Terraform with Checkov`
- `jet pull, commit, push, then run Jenkins`

You can still `@`-mention a skill file (for example `@.cursor/skills/jenkins/SKILL.md`) for an explicit workflow. **Explicit `@` wins** if it ever conflicts with a loose phrase.

---

## 4. Where to add or change things

| You need | Put it in | Why |
|----------|-----------|-----|
| A new **AI policy** or standard | [`rules/`](rules/) as a focused `.mdc` | Rules load for the model; keep each file small and scoped with `globs` when possible. |
| A new **multi-step agent workflow** | [`skills/<id>/SKILL.md`](skills/) | Skills carry triggers, safety gates, and command sequences. |
| A **CLI helper** used by skills | [`scripts/`](scripts/) | Runnable from repo root; document with `--help` / [`scripts/README.md`](scripts/README.md). |
| A **registered tool** with a formal contract | [`tools/`](tools/) + row in [`tools/readme.md`](tools/readme.md) + `*.TOOL.md` | Single registry for discoverability and Pydantic-style inputs (see registry for the checklist). |
| A **working automation note** | [`plans/`](plans/) | Short-lived engineering plans; use **ADR** in `docs/adr/` for architecture decisions. |

After adding a skill or a major tool category, add **one row** to [`.cursor/JET.md`](JET.md) so the coarse routing table stays accurate.

---

## 5. Top-level folders

| Path | Purpose |
|---|---|
| [`JET.md`](JET.md) | **Natural-language entry contract** — optional `jet` keyword, coarse intent → skill/rule routing, extension rules. |
| [`rules/`](rules/) | **Agent rules** (`.mdc`): always-on or scoped guidance — architecture, VPC/jumpbox constants, Jenkins CLI policy, documentation scope, script README policy, debugging via jumpbox. |
| [`skills/`](skills/) | **Agent skills** (one folder per skill, each with `SKILL.md`): git pull/commit/push, Jenkins trigger/watch, Terraform validation and module patterns, AWS connectivity and security-group checks, **`kt_buddy`** solution guide. |
| [`scripts/`](scripts/) | **Runnable helpers** (Python, shell): Terraform Checkov wrapper, EKS pre/post validation, ACM/ALB cert helper — see [`scripts/README.md`](scripts/README.md). Not wired into `deploy/Jenkinsfile_Deploy_App` unless explicitly integrated. |
| [`tools/`](tools/) | **Skill-invoked tools**: Python utilities (**[`jenkins_tools.py`](tools/jenkins_tools.py)** Jenkins CLI), **`readme.md`** registry plus `*.TOOL.md` descriptors (inputs, safety, examples). |
| [`validation/`](validation/) | **Markdown specifications** that pair with scripts (for example EKS pre-deploy validation criteria referenced by `pre-deploy-validate-eks.sh`). |
| [`config/`](config/) | **Operator reference** (for example EKS cluster settings) — factual snapshots or checklists, not application runtime config. |
| [`plans/`](plans/) | **Working plans** (Markdown): agent or engineer notes for upcoming automation or fixes; not a substitute for ADRs in `docs/adr/`. |
| [`commands/`](commands/) | **Placeholder** for Cursor custom slash-command definitions if the team adds them later (directory may be empty). |
| [`scratch/`](scratch/) | **Optional local scratch** for ephemeral notes or experiments; keep out of committed deliverables unless intentionally shared. |
| [`todo/`](todo/) | **Optional** task stubs for agent workflows (directory may be empty). |

---

## 6. Related paths

| Path | Relationship |
|---|---|
| [`README.midas.md`](../README.midas.md) | Solution documentation index — includes **§2.4** linking back to this file. |
| [`deploy/scripts/README.md`](../deploy/scripts/README.md) | Pipeline and operator scripts used by Jenkins (`ci/`, `dev/`, `test/`, `util/`) — distinct from **`.cursor/scripts/`**. |
| [`.cursor/rules/doc.mdc`](rules/doc.mdc) | When READMEs under `docs/`, `deploy/`, or `.cursor/scripts/` change, follow documentation scope rules. |

---

## 7. Conventions

- **Rules:** Prefer small, focused `.mdc` files; use `solution_const.mdc` identifiers verbatim when scripts or docs mention VPC, region, Transit Gateway, or jumpbox.
- **Skills:** Each skill is self-contained under `skills/<name>/SKILL.md`; trigger phrases and workflows live in that file.
- **Scripts:** Prefer `--help` and clear env vars; see **`.cursor/rules/scripts_docs.mdc`**.
- **Secrets:** Never commit API tokens, passwords, or private keys into `.cursor/` (or anywhere in the repo).

---

## 8. Restructure and cleanup plan

For phased **rename hygiene**, deduplication of Jenkins/git skills, optional `AGENTS.md`, and verification steps, see [`.cursor/plans/2026-04-18-cursor-jet-entry-and-restructure.plan.md`](plans/2026-04-18-cursor-jet-entry-and-restructure.plan.md).

---

<div align="center">
  <sub>
    MIDAS · Managed Intelligent Data Analytics Solution<br/>
    Cursor workspace guide · version 1.1.0 · 2026-04-18
  </sub>
</div>
