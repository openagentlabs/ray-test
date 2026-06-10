# `aspire.svc/services/` — backend-shaped domains

First-level folders here are **bounded contexts** (microservice-shaped): each gets a public **`index.ts`** and **no** deep imports from outside. **`aspire.svc/`** currently has **no** service packages under this directory; the prior **`persistence/`** domain was removed because nothing in the UI host used it.

When you add a domain (e.g. **`aspire.svc/services/persistence/`** again, or another name):

- Export only through **`@/services/<name>`** (the barrel).
- Keep drivers, repositories, and migrations **inside** that folder.

Rules: **`aspire.svc/.cursor/rules/architetcure.mdc`**, **`aspire.svc/.cursor/rules/database.mdc`**. Narrative: **`doc/solution-architecture/modular-monolith.md`**.
