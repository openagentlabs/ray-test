# file-system-client (TypeScript)

High-performance Node.js library for reading and writing text and binary files with typed `Result` error handling (`neverthrow` + Zod).

Mirror of `clients/file-system/py` — same `Cluster` facade, engine layering, and error codes, implemented with TypeScript best practices.

---

## Introduction

Import `Cluster` for a single typed entry point to local file I/O. Expected failures return `Err(AppError)`; unexpected errors propagate to the caller.

`Cluster` wraps a pluggable `FileEngine`. The default `NativeFileEngine` uses Node `fs` with buffered reads, a large-file read path, and atomic temp-file writes.

---

## The `Cluster` class

| Method | Returns | Purpose |
|--------|---------|---------|
| `readBytes(path)` | `BytesResult` | Read a file as `Buffer` |
| `writeBytes(path, data)` | `UnitResult` | Write raw bytes |
| `readText(path, encoding?)` | `TextResult` | Read and decode text |
| `writeText(path, text, encoding?)` | `UnitResult` | Encode and write text |

```typescript
import { Cluster, TextEncoding } from "file-system-client";

const cluster = new Cluster();
const outcome = cluster.readText("config/settings.json");

if (outcome.isErr()) {
  throw new Error(outcome.error.message);
}

const text = outcome.value;
```

### When to use `Cluster`

**Use when:** local text/binary I/O with structured errors, Zod ingress validation, and parity with the Python client.

**Do not use when:** streaming large files, async-only pipelines, or cloud storage — use streaming APIs or the storage client instead.

---

## Install and test

```bash
cd clients/file-system/ts
npm install
npm run build
npm test
npm run test:unit
npm run test:integration
```

---

## Layout

| Path | Role |
|------|------|
| `src/cluster.ts` | Public `Cluster` wrapper |
| `src/io/engine.ts` | `FileEngine` base + `NativeFileEngine` |
| `src/core/` | `AppError`, `Result` aliases, error mapping |
| `src/domain/` | Enums and Zod schemas |
| `src/validation/` | Ingress validation |
| `testing/unit/` | Unit tests |
| `testing/integration/` | Integration tests |

---

## Related

- Python twin: `clients/file-system/py`
- TypeScript conventions: `.cursor/rules/typescript.mdc`
- Vitest layout: `.cursor/rules/testing_ts.mdc`
