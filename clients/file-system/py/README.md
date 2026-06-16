# file-system-client

High-performance Python library for reading and writing text and binary files with typed `Result` error handling.

---

## Introduction

This library gives application code a single, typed entry point for local file I/O. Instead of scattering raw `open()` calls and ad hoc exception handling across your app, you import `Cluster` and work with explicit `Success` / `Failure` results.

`Cluster` is a thin wrapper around a pluggable `FileEngine`. By default it uses `NativeFileEngine`, which reads and writes through optimized stdlib paths (buffered I/O, memory mapping for large reads, atomic writes via a temp file). Validation runs at the boundary; known problems such as missing files, permission errors, and encoding failures come back as structured `AppError` values. Unexpected errors are not swallowed—they propagate to the caller.

Use this library when you want fast, consistent file access with predictable error handling that matches the rest of this repository’s Python style (`returns`, Pydantic, strict typing).

---

## The `Cluster` class

`Cluster` is the public facade you should import into application code. It exposes four methods:

| Method | Returns | Purpose |
|--------|---------|---------|
| `read_bytes(path)` | `BytesResult` | Read a file as raw bytes |
| `write_bytes(path, data)` | `UnitResult` | Write raw bytes (replaces existing content) |
| `read_text(path, encoding=...)` | `TextResult` | Read and decode a text file |
| `write_text(path, text, encoding=...)` | `UnitResult` | Encode and write a text file |

Create one instance and reuse it, or inject a custom engine for tests:

```python
from file_system import Cluster, NativeFileEngine

cluster = Cluster()                          # default engine
cluster = Cluster(engine=NativeFileEngine()) # explicit engine
```

### When to use `Cluster`

**Use `Cluster` when:**

- Application or service code needs to read or write local text or binary files.
- You want expected I/O failures (file not found, permission denied, bad encoding) returned as `Failure(AppError)` instead of raised exceptions.
- You need a stable, typed API that validates paths and payloads before touching the filesystem.
- You read or write files that may be large and benefit from mmap reads and atomic writes without managing those details yourself.

**Do not use `Cluster` when:**

- You need streaming or partial reads/writes over very large files (this library reads/writes whole file content in memory).
- You need async I/O (`asyncio` / `aiofiles`)—`Cluster` is synchronous.
- You need cloud or remote storage (S3, network mounts with special semantics)—use the appropriate storage client instead.
- You only need a one-off script with no error discipline—plain `pathlib` may be enough.

For advanced cases (custom backends, benchmarks, unit tests), implement or subclass `FileEngine` and pass it to `Cluster(engine=...)`. Most application code should stay on the default `Cluster()` and never touch the engine directly.

---

## 1. Purpose

Importable client library under `clients/file-system/py` that wraps a fast stdlib-based engine behind a `Cluster` facade. Expected failures (missing paths, permissions, encoding errors) return `Failure(AppError)`; unexpected errors propagate to the caller.

---

## 2. Stack

| Item | Value |
|------|-------|
| Python | 3.12+ |
| Packaging | uv / setuptools (`src/` layout) |
| Validation | Pydantic v2 |
| Results | `returns` (`Success` / `Failure`) |

---

## 3. Install and run

From this directory:

```bash
cd clients/file-system/py
uv sync --dev
uv run pytest
uv run pytest testing/unit
uv run pytest testing/integration
uv run mypy
```

Use in application code (after `uv sync` in this tree or installing the package):

```python
from returns.result import Failure

from file_system import Cluster, TextEncoding

cluster = Cluster()
outcome = cluster.read_text("config/settings.json")

if isinstance(outcome, Failure):
    err = outcome.failure()
    raise RuntimeError(err.message)

text = outcome.unwrap()
```

---

## 4. Layout

| Path | Role |
|------|------|
| `src/file_system/cluster.py` | Public `Cluster` wrapper |
| `src/file_system/io/engine.py` | `FileEngine` base + `NativeFileEngine` |
| `src/file_system/core/` | `AppError`, `Result` aliases, error mapping |
| `src/file_system/domain/` | Enums and Pydantic models |
| `src/file_system/validation/` | Ingress validation |
| `testing/unit/` | Unit tests (validation, error mapping, engine, delegation) |
| `testing/integration/` | Integration tests (`Cluster` + real temp filesystem) |
| `testing/conftest.py` | Shared pytest fixtures |

---

## 5. Public API

- `Cluster` — `read_bytes`, `write_bytes`, `read_text`, `write_text`
- `NativeFileEngine` — injectable engine (mmap for reads > 16 MiB, atomic temp-file writes)
- `TextEncoding` — `UTF8`, `UTF16`, `ASCII`, `LATIN1`
- `AppError`, `ErrorCodes`, `Success`, `Failure`, `FsResult` aliases

---

## 6. Related

- Python conventions: `.cursor/rules/python/python.mdc`
- Error handling: `.cursor/rules/error/error.mdc`
