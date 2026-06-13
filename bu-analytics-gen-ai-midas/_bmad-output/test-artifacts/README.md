# Test artifacts (TEA module)

Configured in `_bmad/tea/config.yaml`:

| Path | Purpose |
|---|---|
| `test-design/` | Test design outputs |
| `test-reviews/` | Test review outputs |
| `traceability/` | Requirements traceability |

## Relationship to scenario test gate

**pytest + Vitest** (see `_bmad-output/testing/scenario-test-gate.md`) are the **mandatory** gate for scenarios 1–3.

## SME reviews (formulas & data science)

When tests validate **business formulas**, **training**, or **metrics**:

```
test-artifacts/sme-reviews/<slug>/ST-NNN/
  sme-review-package.md    # agent creates — developer sends to SME
  sme-signoff.md           # human records SME verdict
```

Policy: `_bmad-output/testing/sme-verification-gate.md`  
Templates: `templates/sme-review-package-template.md`, `templates/sme-signoff-template.md`

Use `bmad-qa-generate-e2e-tests` and TEA workflows when you need deeper API/E2E design — they supplement, not replace, unit/integration tests. Formula-heavy tests still require SME sign-off.
