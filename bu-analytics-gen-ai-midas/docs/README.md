<!--
  docs/README.md — entry when browsing the docs/ folder on a Git host.
  The repository root README.md is now the Atlas landing page.
  The long-form MIDAS overview was renamed to ../README.midas.md.
  Follow .cursor/rules/doc.mdc when editing documentation in docs/.
-->

# EXLdecision documentation (`docs/`)

**Git hosting shows the repository README at the repository root.** That page is now the **Atlas** landing — the visual entry point to the project — see [`README.md` (repository root) →](../README.md).

The long-form MIDAS solution overview (formerly the root README) has been preserved at:

**[`README.midas.md` (repository root) →](../README.midas.md)**

That document includes the overview, **Getting started**, document index, changelog, and glossary.

## In this folder

| Resource | Description |
|---|---|
| [`infrastructure.md`](infrastructure.md) | Platform overview — accounts, VPC, network, pipelines, IaC conventions |
| [`aws-resource-naming-conventions.md`](aws-resource-naming-conventions.md) | Mandatory AWS naming patterns |
| [`guardrails-developer-guide.md`](guardrails-developer-guide.md) | **AI Gateway guardrails** — 4 `exlerate-*` Bedrock Guardrail profiles, PII coverage, request flow, decision guide, test commands, and team/key/request assignment |
| [`images/`](images/) | Documentation assets (for example the EXL Service logo used by the root README) |

## Companion: Atlas

A standalone, browser-only React SPA that gives a guided, interactive map of
the solution. It is decoupled from the rest of the codebase and is meant to
be opened in a separate tab when reading the README.

- Source: [`atlas/`](../atlas/)
- Notes for AI agents: [`atlas/agent/README.md`](../atlas/agent/README.md)
- Hosted URL: _set this once Atlas is deployed to Pages / S3._

Other guides are linked from the [MIDAS document index](../README.midas.md#2-document-index).
