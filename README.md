# EXLdecision.AI

## Transform Your Data into Actionable Intelligence

The most comprehensive analytics platform with AI-powered insights, synthetic data generation, and advanced modeling capabilities designed for modern businesses.

<div align="left">

<small>

| | |
|:--|:--|
| **Version** | 1.0.0 |
| **Updated** | 2026-06-14 12:00 UTC |
| **Owner** | platform@example.com |

</small>

</div>

---

Human-oriented guides for the Ray Test monorepo: Cursor rules, web-app UI standards, observability, and runnable examples.

## Table of contents

- [Cursor rules in this solution](doc/rules.md)
- [Agent skills hub](skills/README.md)
- [Web-app responsive design guide](doc/web-design/web-design.md)
- [Web-app page authoring rules](doc/web-design/web-app-pages.md)
- [EXL Observability — Developer Guide](doc/observibility/observability-guide.md)
- [EXL Observability — Cursor Agent Rules](doc/observibility/observability-rules.md)
- [Distributed Ray hello-world](doc/examples/ray_hello_world.py)

---

## Testing

Python packages and microservices in this monorepo use **pytest** as the mandatory test runner. We do not enumerate individual tests here — they change frequently — but every package follows the same layout, framework, and run patterns documented in **`.cursor/rules/testing_py/testing_py.mdc`**.

### Framework and layout

| Package kind | Test root | Typical subfolders |
|---|---|---|
| Microservice (`*.svc/server/`) | `tests/` | `unit/`, `integration/`, `database/`, `user/` |
| UV tool or Python client | `testing/` | `unit/`, `integration/`, `user/` |

- **pytest** + **pytest-asyncio** (`asyncio_mode = "auto"`)
- One test file per subject; user-case tests cover invalid inputs and edge paths, not only happy path
- Service code uses `returns` `Result` — tests assert both `Success` and `Failure` branches
- Agents report results using the traffic-light table format defined in the testing rule

### Run commands

From the package root (example: IAM server):

```bash
cd iam.svc/server && uv sync --dev && uv run pytest
```

| Goal | Command |
|---|---|
| Full suite | `uv run pytest` |
| One file | `uv run pytest tests/unit/test_<subject>.py -v` |
| One test | `uv run pytest tests/unit/test_<subject>.py::test_<name> -v` |

TypeScript clients in this repo use **Vitest** — see each client `package.json` (`npm test`).

### Single-test shape

A minimal unit test matches this pattern (docstring becomes the agent feedback **Description** column):

```python
def test_returns_failure_for_empty_input() -> None:
    """User case: empty input yields validation Failure."""
    outcome = validate_request("")
    assert isinstance(outcome, Failure)
    assert outcome.failure().code == "validation"
```

Canonical policy: **`.cursor/rules/testing_py/testing_py.mdc`**.

---

## Related canonical references

| Topic | Path |
|-------|------|
| Monorepo layout and dev ports | `.cursor/rules/solution/solution.mdc` |
| Project constants (`PRJ_*`, `AWS_*`, …) | `.cursor/rules/constants/constants.mdc` |
| README policy per folder | `.cursor/rules/docs/docs.mdc` |
| Rule file meta-policy | `.cursor/rules/rules/rules.mdc` |
| Agent skills hub | `skills/README.md` · router `.cursor/skills/ray-test/SKILL.md` |
| `web-app/` run instructions | `web-app/README.md` |
| `exl-observability` library | `lib/exl-observability/README.md` |
