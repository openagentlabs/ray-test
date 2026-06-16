# Ray Test skills

Modular agent skills for this monorepo. Each skill lives in its own folder under **`skills/<id>/`** with separation of concerns (workflow, reference, and shared DSL docs).

## Entry point

Start with the **ray-test** router:

- **`.cursor/skills/ray-test/SKILL.md`** — helps you pick a skill, confirms intent, then delegates to **`skills/<id>/SKILL.md`**

Say **`ray-test`**, **`skills`**, or describe your task; the agent routes you to the right folder.

## Catalog

See **`skills/catalog.md`** for the full list, trigger phrases, and paths.

## Layout

```
skills/
├── catalog.md              # Machine-readable index for the router
├── README.md               # This file
├── _shared/
│   └── workflow-reference.md
├── tf/
├── prj/
├── aws_dynamodb_create/
├── aws_s3_create/
└── rules-create/
```

Legacy **`.cursor/skills/<id>/SKILL.md`** stubs redirect here for `@` mentions and old links.

## Adding a new skill

1. Create **`skills/<folder>/`** with **`SKILL.md`** (and optional `workflow.md`, `reference.md`).
2. Add a row to **`skills/catalog.md`** (id, folder, triggers, summary).
3. Add a thin redirect stub at **`.cursor/skills/<id>/SKILL.md`** pointing to **`skills/<folder>/SKILL.md`** with `disable-model-invocation: true`.
4. Update **`.cursor/rules/tool/tool.mdc`** index if the skill is repo-wide tooling.

Do not put full skill bodies under **`.cursor/skills/`** — only the **ray-test** router and redirect stubs belong there.

## Related

| Topic | Path |
|-------|------|
| Tooling index | `.cursor/rules/tool/tool.mdc` |
| Rule meta-policy | `.cursor/rules/rules/rules.mdc` |
