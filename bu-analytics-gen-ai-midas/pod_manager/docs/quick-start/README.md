# Quick start

Use **local** for day-to-day development on your machine, or **AWS** after the dev EKS stack is provisioned.

| Path | Guide |
|------|--------|
| **Local** | [local.md](local.md) — Docker Compose stack, CLI, web test client |
| **AWS** | [aws.md](aws.md) — Terraform, Helm, EKS deploy, `dev-test` |

Endpoint profiles: [`config/deploy/`](../../config/deploy/) (`local.env` and generated `aws.env`).

## Run from this doc (Cursor / VS Code)

Open a quick-start guide in the **workspace** (trusted). Each step has a **▶ Run** link that runs a matching task in the integrated terminal so you can watch output there.

- **Preview:** `Ctrl+Shift+V` (or **Markdown: Open Preview**) — click **▶ Run** links in the preview.
- **Editor:** `Ctrl+Click` the same links in the source view.
- **Tasks menu:** `Terminal` → `Run Task…` → pick `qs-local-*` or `qs-aws-*` (defined in [`.vscode/tasks.json`](../../.vscode/tasks.json)).
- **Shell blocks:** You can also use **Run in Terminal** above `bash` code blocks if your editor shows it (trusted workspace).

Long-running steps (local stack, Next.js dev server, `terraform apply`) may take several minutes; keep the terminal open until they finish.
