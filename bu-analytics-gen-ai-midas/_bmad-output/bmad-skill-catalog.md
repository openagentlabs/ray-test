# Local BMad skill catalog (MIDAS)

Official `_bmad/_config/bmad-help.csv` is **missing** in this install. This file is a **manual index** of installed skills (`.agents/skills/`) for routing. Re-run the BMad installer to generate the CSV if `bmad-help` requires it.

| Skill | Invoke phrase | Menu code | Module | Notes |
|---|---|---|---|---|
| `bmad-help` | bmad help / what next | — | core | Reads config + artifacts |
| `bmad-spec` | create a spec / distill into spec | — | bmm | Output: `_bmad-output/specs/` |
| `bmad-prd` | create or validate PRD | — | bmm | Replaces deprecated create/edit/validate-prd |
| `bmad-prfaq` | PRFAQ / work backwards | **WB** | bmm | manifest only |
| `bmad-create-story` | create the next story | — | bmm | |
| `bmad-dev-story` | dev this story | — | bmm | Loads project-context |
| `bmad-quick-dev` | quick fix / small feature | — | bmm | |
| `bmad-code-review` | run code review | — | bmm | |
| `bmad-investigate` | investigate bug | — | bmm | |
| `bmad-create-architecture` | create technical architecture | — | bmm | |
| `bmad-technical-research` | technical research report | — | bmm | |
| `bmad-ux` | create UX specifications | — | bmm | |
| `bmad-qa-generate-e2e-tests` | create qa automated tests | — | bmm | |
| `bmad-checkpoint-preview` | checkpoint / human review | — | bmm | |
| `bmad-review-edge-case-hunter` | edge case analysis | — | bmm | |
| `bmad-review-adversarial-general` | cynical review | — | bmm | |
| `bmad-generate-project-context` | generate project context | — | bmm | |
| `bmad-document-project` | document this project | — | bmm | |
| `bmad-party-mode` | party mode | — | bmm | |
| `bmad-advanced-elicitation` | socratic / red team | — | bmm | |
| `bmad-agent-architect` | talk to Winston | — | bmm | |
| `bmad-agent-dev` | talk to Amelia | — | bmm | |
| `bmad-agent-pm` | talk to John | — | bmm | |
| `bmad-agent-analyst` | talk to Mary | — | bmm | |
| `bmad-agent-ux-designer` | talk to Sally | — | bmm | |
| `bmad-agent-tech-writer` | talk to Paige | — | bmm | Multi-action: WD, VD, EC, MG |
| `bmad-create-epics-and-stories` | create epics and stories | — | bmm | |
| `bmad-sprint-planning` | sprint planning | — | bmm | |
| `bmad-sprint-status` | sprint status | — | bmm | |
| `bmad-check-implementation-readiness` | implementation readiness | — | bmm | |
| `bmad-correct-course` | correct course | — | bmm | |
| `bmad-retrospective` | retrospective | — | bmm | |
| `bmad-brainstorming` | help me brainstorm | — | bmm | |
| `bmad-domain-research` | domain research | — | bmm | |
| `bmad-market-research` | market research | — | bmm | |
| `bmad-product-brief` | product brief | — | bmm | |
| `bmad-shard-doc` | shard document | — | bmm | |
| `bmad-index-docs` | index docs | — | bmm | |
| `bmad-customize` | customize bmad | — | core | |

**Deprecated:** `bmad-create-prd`, `bmad-edit-prd`, `bmad-validate-prd` → use `bmad-prd`.
