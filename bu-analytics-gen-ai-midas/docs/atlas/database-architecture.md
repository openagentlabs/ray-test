# Database architecture

The Atlas data layer is five layers deep, each one calling the next. The
layering is non-negotiable: callers higher up the stack never reach more
than one layer down.

```
┌─────────────────────────────────────────────────────────────┐
│  React tree                                                 │
│  - app/**/page.tsx, providers/AppConfigProvider, …          │
│  - calls server actions via plain async function imports    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Server actions (atlas/src/actions/**)                      │
│  - 'use server' on line 1                                   │
│  - Validate inputs with Zod                                 │
│  - Resolve current user / account                           │
│  - Call repositories                                        │
│  - Return POJOs (records), never class instances            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Repositories (atlas/src/lib/db/repositories/**)            │
│  - Generic abstract `BaseRepository<T, R>`                  │
│  - One concrete subclass per entity                         │
│  - Audit-stamping, soft-delete filtering, transactions      │
│  - Return domain class instances (`User`, `Account`, …)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Entities (atlas/src/lib/db/entities/**)                    │
│  - `BaseEntity` + concrete classes                          │
│  - Zod schemas (the runtime guard + the type source)        │
│  - `fromRecord` / `toRecord` adapters                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Database context (atlas/src/lib/db/context/**)             │
│  - Abstract `DatabaseContext` (engine-agnostic)             │
│  - Concrete `LowDbContext` (single JSON file via lowdb)     │
│  - `transaction(mutator)` is the only write entry point     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
       /tmp/exldecision-atlas/atlas-db.json
```

## Where things live

| Concern | Folder | Owner doc |
|---|---|---|
| Persistent JSON file | `/tmp/exldecision-atlas/` | [`database-selection.md`](database-selection.md) |
| Engine swap point | `atlas/src/lib/db/context/` | [`context/README.md`](../../atlas/src/lib/db/context/README.md) |
| Entity definitions | `atlas/src/lib/db/entities/<entity>/` | [`entity-model.md`](entity-model.md) and per-entity README |
| CRUD + finders | `atlas/src/lib/db/repositories/<entity>/` | per-repository README |
| Bootstrap (seed) | `atlas/src/lib/db/bootstrap.ts` | this file |
| Current user / account helpers | `atlas/src/lib/db/current-context.ts` | this file |
| Server actions | `atlas/src/actions/<area>/` | [`server-actions.md`](server-actions.md) |

## Database context

`DatabaseContext` is **abstract**. Today the only implementation is
`LowDbContext`. It exposes:

| Member | Purpose |
|---|---|
| `data` (getter) | Read-only handle on the in-memory document. |
| `collection(key)` | Typed pointer into one of the entity arrays. |
| `commit()` | Persist the in-memory document to disk. |
| `transaction(mutator)` | The only write entry point repositories use. Holds an FIFO lock on the JS event loop, runs the mutator, writes to disk, releases the lock. |
| `reset()` | Test-only. Empties the document and writes. |

`getDatabaseContext()` is the **process-wide singleton**. The first call
also runs `bootstrapDefaults`, which idempotently seeds:

- The system user (`SYSTEM_USER_ID = 00000000-...-000000000000`).
- The default admin user (`DEFAULT_ADMIN_USER_ID`).
- The default account (`DEFAULT_ACCOUNT_ID`), owned by the admin.
- The default config row attached to the default account.

These reserved IDs are the only stable identifiers in the system.
Everything else is a freshly-generated `crypto.randomUUID()`.

## Repositories

Every concrete repository extends `BaseRepository<T, R>` (generic over
the entity class and its persisted record). The base implements every
contract method on `IRepository`:

- `findById`, `findAll`, `exists`, `count`
- `create`, `update`, `softDelete`, `restore`, `setEnabled`, `hardDelete`

…plus audit stamping (`createdAt`, `updatedAt`, `createdByUserId`,
`updatedByUserId`), default filtering (skip `deleted` and `enabled === false`
unless asked), and write-through-`transaction` discipline.

A concrete repository only supplies four hooks (`entityName`,
`collectionKey`, `parseRecord`, `instantiate`) and any entity-specific
finders (e.g. `UserRepository.findByEmail`).

## Server actions

The React tree never imports a repository. It imports a server action
from `@/actions/<area>/<verb>`. The server action validates input with
Zod, resolves a `MutationContext` via `getCurrentMutationContext()`,
calls the repository, and returns a JSON-safe record.

Sample read:

```ts
'use server'
export async function getCurrentAccountConfig(): Promise<AppConfig> {
  const account = await getCurrentAccount()
  const ctx = await getCurrentMutationContext()
  const repo = await getConfigRepository()
  const cfg = await repo.findOrCreateFor(account.id, ctx)
  return toAppConfig(cfg.body)
}
```

Sample write:

```ts
'use server'
export async function updateCurrentAccountConfig(next: AppConfig): Promise<AppConfig> {
  const validated = AppConfigSchema.parse(next)
  const body = fromAppConfig(validated)
  const account = await getCurrentAccount()
  const ctx = await getCurrentMutationContext()
  const repo = await getConfigRepository()
  const updated = await repo.upsertBody(account.id, body, ctx)
  return toAppConfig(updated.body)
}
```

## Where the React tree connects

`AppConfigProvider` (the only React state we cared about persisting) now:

1. On mount, calls `getCurrentAccountConfig()` and seeds local state.
2. Calls `updateCurrentAccountConfig(next)` on every save.
3. Calls `resetCurrentAccountConfig()` on reset.

The legacy `localStorage`-backed `app-config.store.ts` is gone; what
remains there are pure predicates (`isGitConfigUsable`,
`isBuildStatusFeedUsable`) that operate on an `AppConfig` argument.
