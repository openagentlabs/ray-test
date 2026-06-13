# Style guide — gold standard for the Atlas data layer

These conventions are non-negotiable for any code under `atlas/src/lib/db`,
`atlas/src/actions`, and the providers that talk to them. They were
applied during the initial build-out and any new work has to match.

## TypeScript

| Rule | Why |
|---|---|
| `strict: true` is on. Don't lower it. | Catches the bugs we don't write tests for. |
| **Never use `any`.** Use `unknown` and narrow, or define an interface. | `any` defeats the entire compiler. The few places we cast are commented and minimal. |
| Always provide return types on exported functions. | Makes the public surface obvious from a single skim. |
| Use `interface` for object shapes that may be implemented; `type` for unions, discriminators, mapped types, and `infer<typeof Schema>`. | Conventional split that matches how the IDE behaves. |
| Use `readonly` for entity fields. | Entities are immutable in-memory; mutations go through repositories. |
| Use modern syntax: `??`, `?.`, top-level `await`, `import * as`, etc. | We require Node 20+. |
| Prefer `unknown` over `any` in error handlers. Narrow with `instanceof Error`. | Type-safe error handling. |
| Use Zod (`*Schema`) as the single source of truth for both the runtime guard and the inferred record type. | Pydantic-style: one schema, two outputs. |

## File and folder layout

Per-entity folder layout:

```
<entity>/
├── README.md
├── <Entity>.ts                # schema + class + adapters
└── __tests__/
    └── <Entity>.test.ts
```

Per-repository folder layout:

```
<entity>/
├── README.md
├── <Entity>Repository.ts
└── __tests__/
    └── <Entity>Repository.test.ts
```

Per-action layout:

```
<area>/
├── README.md
├── <verb><Noun>.ts
└── (optional) __tests__/
```

Hard rules:

- Every concept-folder ships its own `README.md`. No exceptions.
- Tests live in `__tests__/` next to the code they exercise. Never in a
  parallel `tests/` tree.
- One file per public concept. No "dump everything in `index.ts`"
  modules.

## Naming

| Concept | Convention | Example |
|---|---|---|
| Entity class | `PascalCase`, singular noun | `Account` |
| Entity record type | `<Entity>Record` | `AccountRecord` |
| Schema | `<Entity>Schema` | `AccountSchema` |
| Repository class | `<Entity>Repository` | `AccountRepository` |
| Singleton accessor | `get<Entity>Repository()` | `getAccountRepository()` |
| Test reset hook | `__reset<Entity>RepositoryForTests()` | `__resetAccountRepositoryForTests()` |
| Server action file | `<verb><Noun>.ts` | `renameAccount.ts` |
| Reserved IDs | `SCREAMING_SNAKE_CASE` constants | `DEFAULT_ACCOUNT_ID` |

## Repository discipline

- Every write goes through `db.transaction()`. No direct mutations of
  `db.data`.
- Audit fields are stamped in `BaseRepository`, never in subclasses.
  Subclasses must not override `create` / `update` / `softDelete` / `restore`
  / `setEnabled` / `hardDelete`.
- Entity-specific finders go on the subclass and follow the naming
  convention `find<Predicate>` (singular) or `find<Predicate>s` /
  `findAll<Predicate>` (plural).
- The repository returns class instances. The action returns records.
  Never let class instances cross the action boundary.

## Server-action discipline

- `'use server'` on line 1.
- Validate inputs with Zod inside the action.
- Resolve the actor through `getCurrentMutationContext()`. Never let
  the client pass the actor id.
- Return `*Record` POJOs. Don't return `User` / `Account` / `Login` /
  `Config` instances.
- Throw plain `Error` on failure. Don't return `{ ok: false, … }`
  envelopes — exceptions are the right channel for Next.js actions.

## Documentation

- The data layer has three layers of documentation, all of which must
  be kept in sync:
  1. The per-folder `README.md` (local view).
  2. The system-wide docs in `docs/atlas/` (this folder).
  3. JSDoc on exported types / functions in source.
- When you add a new entity, server action, or change a contract,
  update **all three** layers in the same commit. Reviewers reject
  drift.

## Imports

- Always use the `@/` path alias for intra-project imports. Don't write
  long `../../../` chains.
- Group imports in three blocks separated by blank lines: built-ins,
  external packages, then `@/` imports.
- Avoid barrel `index.ts` files inside `lib/db/**`. Each consumer
  imports from the concrete file. The lone exception is
  `@/lib/db/context/index.ts` which re-exports the singleton accessors
  and the abstract base.

## Errors

- The data layer throws three kinds of errors today:
  - `EntityNotFoundError` — thrown by `BaseRepository` when an id misses.
  - Plain `Error('…')` — thrown by repositories and actions for domain
    invariants (duplicate email, password too short, etc.).
  - Zod's `ZodError` — surfaces from any `*Schema.parse(...)` call.
- Never swallow errors silently. If you `try { … } catch { /* ignore */ }`
  in this folder, leave a comment explaining why.

## Async / concurrency

- Use `db.transaction(mutator)` for any read-modify-write. The lock is
  process-local and FIFO.
- Don't introduce a separate write path. If you need a new mutation
  shape, add it to `BaseRepository` (so audit-stamping stays uniform).
- Never `await` inside a tight loop where you could batch. Today the
  data sets are small enough that this is cosmetic, but the pattern
  matters.
