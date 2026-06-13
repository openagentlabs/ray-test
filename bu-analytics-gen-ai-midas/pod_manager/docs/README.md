# Documentation index

Guides for developers and DevOps working on the **routing tier** in this repository.

Per-user backend routing on Kubernetes: **Envoy** (data plane) + **router.svc** (control plane) assign each authenticated user to one exclusive backend pod. Login and API traffic enter through a shared ingress; routing decisions come from verified identity, not client-supplied host headers.

## Quick start

| Path | Guide |
|------|--------|
| **Local** | [quick-start/local.md](quick-start/local.md) — Docker Compose stack, CLI, web test client |
| **AWS** | [quick-start/aws.md](quick-start/aws.md) — Terraform, Helm, EKS deploy, `dev-test` |

Runnable **▶ Run** links and IDE task setup: [quick-start/README.md](quick-start/README.md).

## Repository layout

See [overview/repository-layout.md](overview/repository-layout.md).

## Local testing

End-to-end validation on your machine with Docker Compose, three terminals (stack / CLI / web), and optional automation.

| Document | Audience | Summary |
|----------|----------|---------|
| [**local-testing/README.md**](local-testing/README.md) | Everyone | Hub: goals, ports, quick commands |
| [three-terminal-setup.md](local-testing/three-terminal-setup.md) | Dev, DevOps | Which terminal runs what; env vars; startup order |
| [components.md](local-testing/components.md) | Dev, DevOps | Each service alone: purpose, ports, dependencies |
| [architecture-and-flows.md](local-testing/architecture-and-flows.md) | Dev, Architect | How pieces connect; Mermaid call-flow diagrams |
| [apis-and-clients.md](local-testing/apis-and-clients.md) | Dev | gRPC, HTTP, Envoy ext_authz; Python/TS/CLI clients |
| [web-test-client.md](local-testing/web-test-client.md) | Frontend, QA | Next.js UI routes, BFF, user test flows |
| [cli-operator.md](local-testing/cli-operator.md) | Dev, SRE | `pod-manager` commands and CLI-only flows |
| [automated-tests.md](local-testing/automated-tests.md) | Dev, CI | `test-local.sh`, `start-local.sh -t` |
| [troubleshooting.md](local-testing/troubleshooting.md) | Dev, DevOps | Common failures and fixes |

## AWS deployment

| Document | Audience | Summary |
|----------|----------|---------|
| [**DEPLOYMENT_PARAMETERS.md**](DEPLOYMENT_PARAMETERS.md) | Dev, DevOps | Every env var: local vs AWS, source, creator |
| [**ENDPOINTS.md**](ENDPOINTS.md) | Dev, DevOps | Ports, URLs, ALB listeners, request flows |
| [../infra/README.md](../infra/README.md) | DevOps | Terraform, Helm, EKS deploy runbook |
| [../dev_testing/README.md](../dev_testing/README.md) | Dev, QA | Unified `dev-test` runner (local + aws) |

## Plans and reference

| Document | Summary |
|----------|---------|
| [LEASE_RESUME_PLAN.md](LEASE_RESUME_PLAN.md) | Lease resume across disconnect / new device (implementation plan) |
| [FIXUP_PLAN.md](FIXUP_PLAN.md) | Implementation fix-up checklist (historical) |

## Related READMEs in the repo

| Path | Topic |
|------|--------|
| [../router.svc/README.md](../router.svc/README.md) | Control plane layout |
| [../router.svc/server/README.md](../router.svc/server/README.md) | Python server run & test |
| [../pods/README.md](../pods/README.md) | Pool workload pods |
| [../test_client_nextjs/README.md](../test_client_nextjs/README.md) | Test UI package |
| [../pod_manager_cli/README.md](../pod_manager_cli/README.md) | CLI package |
| [../dev_testing/README.md](../dev_testing/README.md) | Integration test runner |

## Solution requirements

In-scope routing-tier rules for agents and reviewers: [../.cursor/rules/solutin_reqs.mdc](../.cursor/rules/solutin_reqs.mdc).
