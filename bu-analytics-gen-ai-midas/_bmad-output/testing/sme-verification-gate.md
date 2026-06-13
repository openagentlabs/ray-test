# SME verification gate (data science & formula logic)

**Applies when:** Automated tests or test artifacts assert **business formulas**, **statistical methods**, **model training behavior**, **evaluation metrics**, or **feature-engineering logic** (not just API shape or UI state).

**Policy:** Development is **not done** until a **human** shares the SME review package with a **Subject Matter Expert (SME)** and records **sign-off**. If the SME rejects or requests changes, fix the feature/tests and re-submit — do not mark the story complete.

Scenarios **1–3** (and scenario **4** when changing ML/data paths) follow this gate in addition to [scenario-test-gate.md](scenario-test-gate.md).

---

## When SME review is required

| Trigger | Examples |
|---|---|
| Formula / metric | Gini, KS, IV, WoE, decile lifts, confusion-matrix rates |
| Training pipeline | Fit/predict contracts, hyperparameters, class weights, early stopping |
| Feature engineering | Binning, encoding, imputation rules from PRD |
| Model evaluation | Charts/tables that depend on computed analytics |
| Bug fix (scenario 3) | Incorrect calculation restored — regression test encodes formula |

**Usually not required:** pure CRUD, auth, routing, loading/empty/error UI, chunked upload plumbing without formula assertions.

When unsure, **default to SME review** for Model Lab work.

---

## Artifact package (agent produces; human shares with SME)

Save under:

```
_bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/
  sme-review-package.md          # summary for SME (required)
  test-files-list.md             # paths + what each test proves
  fixtures-notes.md              # parquet/CSV samples used (paths only if large)
  prd-formula-excerpt.md         # REQ-* + PRD/intake formula wording
  sme-signoff.md                 # human fills after SME responds
```

Template: [_bmad-output/test-artifacts/templates/sme-review-package-template.md](../test-artifacts/templates/sme-review-package-template.md)

---

## Workflow

| Step | Who | Action |
|---|---|---|
| 1 | Agent (`bmad-dev-story` / `bmad-qa-generate-e2e-tests`) | Implement tests; run pytest/Vitest green; **create SME package** if triggers apply |
| 2 | Agent | **Stop** — tell developer to share package with SME; do not claim "done" |
| 3 | **Human (developer)** | Send `sme-review-package.md` + linked test files/fixtures to SME |
| 4 | **SME** | Validates formulas/logic against PRD and domain rules |
| 5 | **Human** | Record outcome in `sme-signoff.md` |
| 6a | Sign-off **approved** | Proceed to `bmad-code-review` / merge |
| 6b | Sign-off **changes requested** | New chat: fix code/tests per feedback → re-run tests → update package → re-submit to SME |

---

## Sign-off record (`sme-signoff.md`)

Required fields:

- SME name / role  
- Date  
- Verdict: **approved** | **changes requested**  
- Scope: REQ-*, CAP-*, ST-*, test files reviewed  
- Feedback summary (if changes requested)  
- Re-review date (if applicable)

**Agents must not** mark development complete without `Verdict: approved` in this file when SME gate applies.

---

## Integration with other gates

| Gate | Order |
|---|---|
| pytest/Vitest green | Before SME package |
| SME sign-off | Before `bmad-code-review` claims story done |
| `bmad-code-review` | After SME approved (or N/A if no SME trigger) |
| Party-mode pre-merge | Can run after SME approved |

---

## Related

- [scenario-test-gate.md](scenario-test-gate.md)
- [How to use BMAD for each scenario.md](../How%20to%20use%20BMAD%20for%20each%20scenario.md)
- `_bmad/custom/bmad-dev-story.toml`
