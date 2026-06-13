<!--
  Natural-language entry contract for MIDAS Cursor agents.
  Complements .cursor/README.md; keep in sync when skills or routes change.
-->

# JET — natural-language entry for MIDAS agents

## What this is

**JET** is an optional **keyword prefix** humans can use when talking to the AI in Cursor. It does **not** invoke a separate program. It is a **routing hint**: when a message starts with `jet` (case-insensitive), the agent should treat everything **after** the keyword as **operator intent**, then **read the right skill, rule, or tool** and act.

Design goals:

1. **One mental model** for the developer: “I prefix with `jet`, then say what I want in plain English.”
2. **Soft binding** — the table below is **guidance**, not a rigid parser. The model should infer intent from context; extend this file only when the team repeatedly sees mis-routing.
3. **Escalation path** — if intent is ambiguous, the agent asks **one** targeted question (or offers 2–3 choices), consistent with existing skills (for example `skills/jenkins/SKILL.md`).

## How to use it (operators)

Examples (any of these shapes are valid):

- `jet start the pipeline to dev and watch it`
- `jet validate terraform under deploy/`
- `jet pull commit push then deploy with Jenkins`
- `jet how do I set up AWS SSO for this repo`

You may omit `jet` entirely; agents still discover work through normal phrasing and `@` references. **JET** is for consistency and discoverability inside the team.

## Routing hints (intent → first place to read)

| Intent family (examples) | Read first | Typical execution path |
|--------------------------|------------|-------------------------|
| Jenkins: trigger, watch, logs, stages, approve, queue, stats | `skills/jenkins/SKILL.md` | `tools/jenkins_tools.py` (see `rules/tool.mdc`) |
| Git pull / commit / push only | `skills/git_pull_commit_push/SKILL.md` | git |
| Git + push + Jenkins deploy (full skill) | `skills/git_pull_commit_push_jenkins_start/SKILL.md` | git + `jenkins_tools.py` |
| Jenkins deploy without git phase | `skills/jenkins_run/SKILL.md` | `jenkins_tools.py` |
| Terraform Checkov / validate-fix loop | `skills/tf_validate/SKILL.md` | `scripts/tf_validate.py` |
| New / extended ecs-app Terraform modules | `skills/tf_add_resource/SKILL.md` | `deploy/ecs-app/` |
| “How do I…”, architecture, which script, SSO, kubectl | `skills/kt_buddy/SKILL.md` | `tools/readme.md` + referenced scripts |
| ALB / ACM / cert helper | `skills/aws/SKILL.md` | `scripts/aww-cert-generate-injector.py` |
| SG / connectivity checks from laptop or Jenkins CIDR | `skills/aws_check_security_group_*/` | AWS CLI patterns in each skill |
| VPC, region, jumpbox, TGW IDs (must be exact) | `rules/solution_const.mdc` | cite verbatim; never guess |
| Pipeline-first policy, no laptop `terraform apply` to shared env | `rules/jenkins.mdc`, `rules/architecture.mdc` | Jenkins only |
| Tool discovery and TOOL.md format | `tools/readme.md` | companion `*.TOOL.md` + script |

If two rows both apply, prefer the **more specific** skill (for example `git_pull_commit_push_jenkins_start` over `jenkins` when the user explicitly asked for git + deploy).

## Relationship to `@` mentions

- `@.cursor/skills/jenkins` (or any skill path) is still the **strongest** signal; use it when you want a specific workflow file opened in context.
- `jet …` is a **lightweight** convention when you do not want to pick a path.
- Agents should **merge** `@` context with `jet` intent; if they conflict, **explicit `@` wins**.

## Safety and mutations

Skills that call Jenkins with `trigger`, `approve`, `abort`, etc., must follow **`jenkins_tools.py`** safety flags (for example `--OK_DELETE_MODIFY`) exactly as documented in the skill — **JET does not bypass those rules.**

## Extending this file (maintainers)

When adding a new skill or a new class of operator requests:

1. Add **one row** to the routing table (intent family → `skills/...` or `rules/...`).
2. Add **2–4 example phrases** in the operator section if they differ from existing patterns.
3. Update **`.cursor/README.md`** “JET” subsection so newcomers see the same route.
4. Prefer **skill-local** trigger phrases inside `SKILL.md` front-matter for fine-grained discovery; keep **JET.md** coarse-grained so it stays short.

Do **not** turn this file into a full duplicate of every skill; link out instead.
