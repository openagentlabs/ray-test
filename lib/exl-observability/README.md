# exl-observability

Pluggable async observability for Python microservices.

## Features

- **Five interfaces**: application logging, security logging, distributed tracing, metrics, and APM.
- **Driver architecture**: swap backends without changing application code.
- **AWS CloudWatch drivers**: separate modules for logs, security logs, traces (X-Ray), metrics, and APM events.
- **Minimal hot-path cost**: NoOp drivers when disabled; async batch export when enabled.
- **Structured EXL log format**: JSON lines with stable fields for parsing and alerting.
- **Metrics factory**: enum-validated metric types, groups, and names.
- **Pydantic configuration**: TOML-friendly config sections per interface and driver.
- **Async lifecycle**: `init()` and `shutdown()` on every driver.

## Install

From this monorepo (editable):

```bash
cd lib/exl-observability
uv sync
uv pip install -e .
```

From another service `pyproject.toml`:

```toml
[tool.uv.sources]
exl-observability = { path = "../../lib/exl-observability", editable = true }

[project]
dependencies = ["exl-observability>=0.1.0"]
```

Published install (when published to an index):

```bash
pip install exl-observability
```

## Quick start

```python
from exl_observability.config import ObservabilityConfig
from exl_observability.runtime import ObservabilityRuntime

config = ObservabilityConfig.from_toml_tables({...})
runtime = ObservabilityRuntime(config)
await runtime.init()

logging_client = runtime.logging_client()
logging_client.info("service_started", component="main")

await runtime.shutdown()
```

See `doc/observibility/observability-guide.md` for full usage, configuration, and examples.
