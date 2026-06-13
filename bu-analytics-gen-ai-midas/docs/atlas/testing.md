# Testing

The data layer has 49+ tests today, organised so each entity, repository,
and the database context all carry their own targeted suite. Tests live
in `__tests__/` next to the code they exercise.

## Stack

| Tool | Why |
|---|---|
| **Vitest** v4 | Fast, ESM-native, identical API to Jest. Native TS via Vite. |
| **`@vitest/coverage-v8`** | Coverage reports for the data layer. |
| **`fs.mkdtemp`** | Per-test isolated tmp directory for the lowdb file. |

Configuration lives at [`atlas/vitest.config.mts`](../../atlas/vitest.config.mts).
Important non-default settings:

- `pool: 'forks'` — each test file runs in a real Node process so lowdb
  sees a real fs.
- `environment: 'node'` — no jsdom needed for the data layer.
- `include: ['src/**/__tests__/**/*.test.ts']` — colocated with code.

## Commands

From `atlas/`:

```bash
npm test               # one-shot run, exits non-zero on failure
npm run test:watch     # vitest in watch mode
npm run test:coverage  # writes ./coverage/ HTML + text reports
```

## File layout

```
src/lib/db/
├── context/
│   ├── LowDbContext.ts
│   └── __tests__/
│       └── LowDbContext.test.ts        ← initialises, persists, locks, resets
├── entities/
│   ├── base/
│   │   ├── BaseEntity.ts
│   │   └── __tests__/BaseEntity.test.ts
│   ├── user/
│   │   ├── User.ts
│   │   └── __tests__/User.test.ts      ← schema + class round-trip
│   ├── account/  (same shape)
│   ├── login/    (same shape — also exercises bcrypt)
│   └── config/   (same shape — also tests adapters)
└── repositories/
    ├── base/
    │   ├── BaseRepository.ts
    │   └── __tests__/BaseRepository.test.ts  ← canonical: stamping, soft-delete, errors
    ├── user/
    │   ├── UserRepository.ts
    │   └── __tests__/UserRepository.test.ts  ← findByEmail
    ├── account/  (findByOwner)
    ├── login/    (createEmailPassword + findEmailPassword + markLogin)
    └── config/   (findOrCreateFor + upsertBody)
```

## Canonical fixture pattern

Every repository test starts from a fresh, isolated lowdb file:

```ts
import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { LowDbContext } from '@/lib/db/context'
import { UserRepository } from '@/lib/db/repositories/user/UserRepository'

let tmpDir: string
let users: UserRepository

beforeEach(async () => {
  tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'user-repo-'))
  const ctx = await LowDbContext.initialize({ dir: tmpDir, file: 'db.json' })
  users = new UserRepository(ctx)
})

afterEach(async () => {
  await fs.rm(tmpDir, { recursive: true, force: true })
})
```

This pattern is the **default**. New tests should copy it verbatim
unless they have a strong reason to share state.

## What's covered today

- `DatabaseContext` / `LowDbContext`: empty init, persistence across
  reloads, FIFO transaction lock, `reset()`.
- `BaseEntity`: schema acceptance + rejection on each required field,
  `isActive()`.
- Each entity: complete-record parse, at least one rejection, class
  round-trip.
- `LoginEmailPassword`: bcrypt round-trip, plaintext-length guard,
  `verify` true/false, schema rejects too-short hashes.
- `BaseRepository` (via `UserRepository`): id generation, audit
  stamping, default soft-delete filtering, default disabled filtering,
  `update` immutability of `id` / `createdAt` / `createdByUserId`,
  `EntityNotFoundError`, `hardDelete`, `restore`.
- Per-repo finders: `findByEmail`, `findByOwner`,
  `findEmailPassword`, `markLogin`, `findOrCreateFor`, `upsertBody`.

## Acceptance criteria for new tests

A new entity / repository / action is "done" only when:

1. It has a co-located `__tests__/` folder.
2. The schema is exercised with at least one accepting and one rejecting
   case.
3. The class round-trips through `fromRecord` / `toRecord`.
4. The repository's entity-specific finders each have at least one test.
5. `npm test` is green from a fresh check-out (no skipped tests, no
   focus modifiers).
6. `npm run lint` and `npm run build` are also green.
