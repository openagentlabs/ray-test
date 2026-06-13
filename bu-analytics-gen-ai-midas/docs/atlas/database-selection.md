# Database selection — why `lowdb`

## The constraints

The Atlas companion is a **local developer tool**. It runs as `next dev`
on a contributor's macOS laptop, beside the cloned source code under
`/tmp/exldecision-atlas/`. We needed a persistence layer that:

| # | Constraint | Why it matters |
|---|---|---|
| 1 | NoSQL (document) | Avoid the migration tax of SQL DDL for a tool whose schema will move quickly. |
| 2 | File-based, no server | Zero ops surface; no Postgres, no Mongo, no SQLite daemon. |
| 3 | No native dependencies | Works on any laptop without `node-gyp` / Xcode CLT pain. |
| 4 | Active maintenance | Production-grade reliability for the EXLdecision surface area, not a hobby project. |
| 5 | Native TypeScript types | Aligns with the rest of the Atlas codebase (TS strict, Zod-validated). |
| 6 | Good documentation | A new contributor can learn it in an hour. |

## The candidates

| Library | File-based | Active | TS-native | Native deps | Verdict |
|---|---|---|---|---|---|
| **`lowdb` v7** | Single JSON file | Yes — typicode (json-server author), v7 in 2024 | Yes — TypeScript rewrite | None | **Selected.** |
| `@seald-io/nedb` | One file per collection | Fork-maintained | Bolt-on `@types` | None | Smaller community than lowdb. |
| `lokijs` | Single JSON file | Sporadic releases | Bolt-on `@types` | None | Maintenance has slowed; risk for prod deps. |
| `pouchdb` | Yes (with `leveldb` adapter) | Yes — CouchDB ecosystem | Bolt-on `@types` | `leveldown` → `node-gyp` builds | Heavyweight; install pain on Apple Silicon. |
| `tingodb` | One file per collection | Last release > 3 years | None | None | Effectively abandoned. |
| `better-sqlite3` (with JSON columns) | Single SQLite file | Yes | Yes | Native build (`node-gyp`) | SQL, not NoSQL. Native build pain. |

## Why `lowdb` wins

- **Single file** is the closest analogue to "SQLite for documents". One
  artifact to inspect, copy, delete, version, or `cat`.
- **Atomic writes** are handled by `steno` (write to `.tmp`, `rename`).
  We get crash-safety without paying for a server.
- **Pure JS, no `node-gyp`.** Installs cleanly on every Atlas contributor
  laptop without Xcode CLT or rebuilds.
- **TypeScript-first.** Generic `Low<T>` carries the schema all the way
  through; we never need `@types/lowdb`.
- **Tiny surface.** `db.read()`, `db.write()`, `db.data`. The repository
  layer wraps the rest. A new contributor learns lowdb in five minutes.
- **Active maintenance.** v7 (2024) was a complete TypeScript rewrite by
  the author of `json-server` (~21k stars, pinged regularly).
- **Excellent docs.** The [project README](https://github.com/typicode/lowdb)
  doubles as a tutorial.

## Trade-offs we accepted

- **Whole-file write per save.** For our four-entity, single-laptop tool
  with hundreds of rows at most, this is a non-issue. If the file ever
  approached a megabyte we would revisit (split-collection adapter, swap
  to PouchDB), but that is years away.
- **No query language.** We cannot write `WHERE x AND y ORDER BY z`. The
  repositories use `.find()`, `.filter()`, `.map()`. For this size, that
  is faster *and* more debuggable than a query DSL.
- **No multi-process locking.** lowdb's lock is advisory and per-process.
  Atlas is a single-process dev tool, so this matches reality. The
  abstract `DatabaseContext` makes the lock concern explicit; if we ever
  ran multi-process, we would swap the implementation.

## Gotchas already hit

> `JSONFilePreset` swaps in an in-memory adapter when `NODE_ENV === 'test'`.

This silently dropped every write inside `vitest`. We bypass the preset
and instantiate `Low(new JSONFile(path), default)` directly so production
and tests use the same code path. See
[`LowDbContext.ts`](../../atlas/src/lib/db/context/LowDbContext.ts) for
the comment that pins this in code.

## Replacing lowdb later

The data layer is wrapped behind the abstract `DatabaseContext`. To swap
engines:

1. Add `MyOtherContext extends DatabaseContext` that implements `data`,
   `commit`, `transaction`, `reset`.
2. Change one line in
   [`getDatabaseContext()`](../../atlas/src/lib/db/context/LowDbContext.ts)
   to construct the new class.
3. Repositories, entities, and server actions stay untouched.

This is the whole reason `DatabaseContext` is abstract.
