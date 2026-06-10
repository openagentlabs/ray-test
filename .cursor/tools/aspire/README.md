# aspire-registry-tool

UV-managed CLI under **`.cursor/tools/aspire`**: inspect the **Arb Aspire** `service-registry.sqlite` layout (AI manifest), and **add / list / remove** rows in `registered_services` (same schema as `aspire.svc/` + `scripts/booter.mjs`).

## Setup

```bash
cd .cursor/tools/aspire
uv sync
```

## Run

```bash
uv run aspire-tool              # JSON tool manifest (no flags)
uv run aspire-tool -l           # list services as JSON
uv run aspire-tool -a -p /path/to/bin -n "My Service" -d "Desc"
uv run aspire-tool -r -i <row_id>
```

Default DB path: **`./aspire.svc/service-registry.sqlite`** relative to the current working directory, or override with **`ASPIRE_REGISTRY_DB`**.

## Tests (gold standard: pytest)

```bash
cd .cursor/tools/aspire
uv run pytest
```

See **`.cursor/rules/python.mdc`** for project-wide Python testing and quality rules.
