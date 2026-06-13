# Atlas — data layer documentation

Atlas (the EXLdecision companion app under [`atlas/`](../../atlas/)) now
ships with an embedded NoSQL database, a typed entity / repository layer,
and a server-action surface that the React tree calls instead of writing
to `localStorage`.

This folder is the canonical reference for how that data layer is
designed, why each choice was made, and what acceptance criteria it has
to meet. Read these in order:

| # | Doc | What it covers |
|---|---|---|
| 1 | [`database-selection.md`](database-selection.md) | Why `lowdb`. The candidates we evaluated and the rejection rationale. |
| 2 | [`database-architecture.md`](database-architecture.md) | Context → repositories → entities → server actions → React. Diagrams and contracts. |
| 3 | [`entity-model.md`](entity-model.md) | The four entities (`User`, `Account`, `Login`, `Config`), their fields, relationships, invariants. |
| 4 | [`server-actions.md`](server-actions.md) | The `actions/` folder layout, conventions, and one entry per concrete action. |
| 5 | [`testing.md`](testing.md) | Vitest setup, fixture patterns, acceptance criteria, and how to add a new entity test. |
| 6 | [`style-guide.md`](style-guide.md) | Gold-standard conventions: TypeScript, file layout, READMEs, naming, error handling. |

Each entity and repository folder under `atlas/src/lib/db/` also has its
own `README.md` describing that one concept in detail. The docs in this
folder are the **system-wide** view; the per-folder READMEs are the
**local** view.

## TL;DR for a new contributor

1. The store is a single JSON file under `/tmp/exldecision-atlas/atlas-db.json`,
   managed by [`lowdb`](https://github.com/typicode/lowdb).
2. There are exactly four entities: `User`, `Account`, `Login`, `Config`.
3. `Account` is the **central** entity — every login and config row hangs
   off an account.
4. The React tree calls **server actions** in `atlas/src/actions/`. It
   does **not** import repositories directly.
5. There is exactly one place to look for "how do I auth-stamp this
   field?" → [`BaseRepository`](../../atlas/src/lib/db/repositories/base/README.md).
6. Tests live in `__tests__/` next to the code they exercise. Run them
   with `npm test` from `atlas/`.
