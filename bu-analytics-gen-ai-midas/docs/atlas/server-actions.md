# Server actions

Every call from the React tree into the backend is a Next.js
**server action**. Server actions live in `atlas/src/actions/` and are
the *only* sanctioned transport — there are no REST endpoints for the
data layer.

## Folder layout

```
atlas/src/actions/
├── README.md            ← top-level conventions
├── users/
│   ├── README.md
│   ├── createUser.ts
│   ├── listUsers.ts
│   └── softDeleteUser.ts
├── accounts/
│   ├── README.md
│   ├── createAccount.ts
│   ├── listAccountsForCurrentUser.ts
│   └── renameAccount.ts
├── logins/
│   ├── README.md
│   ├── createEmailPasswordLogin.ts
│   └── verifyEmailPasswordLogin.ts
└── config/
    ├── README.md
    ├── getCurrentAccountConfig.ts
    ├── updateCurrentAccountConfig.ts
    └── resetCurrentAccountConfig.ts
```

One file per action. The named export equals the file name. This makes
imports trivially refactorable and makes the IDE's "go to definition"
unambiguous.

## File contract

```ts
'use server'                                          // line 1, always

import { z } from 'zod'

import { /* repo singletons */ } from '@/lib/db/repositories/...'
import { getCurrentMutationContext } from '@/lib/db/current-context'

const InputSchema = z.object({ /* ... */ })           // co-located schema
export type CreateXInput = z.infer<typeof InputSchema>

export async function createX(input: CreateXInput): Promise<XRecord> {
  const parsed = InputSchema.parse(input)             // never trust client
  const ctx = await getCurrentMutationContext()
  const repo = await getXRepository()
  const x = await repo.create(parsed, ctx)
  return x.toRecord()                                 // POJO out, not class
}
```

Required:

1. `'use server'` on line 1.
2. Inputs validated with Zod *inside* the action.
3. `MutationContext` resolved via `getCurrentMutationContext()` for
   every write.
4. Returns plain JSON-serialisable records (`*Record`), not domain class
   instances. Records cross the network safely; classes do not.
5. Throw `Error(message)` on failure. Do not return error envelopes.

## Why server actions over route handlers?

| Concern | Server action | Route handler |
|---|---|---|
| Boilerplate | None — direct async function | `Request` / `Response`, JSON wrapping |
| Type-safety end-to-end | Yes | No (string URLs, untyped JSON) |
| CSRF | Built-in (Next encodes a token) | DIY |
| Streaming | Yes (Next handles RSC payload) | Manual `ReadableStream` |
| When to prefer | Anything reading or writing the DB | Spawning subprocesses (e.g. `git clone`), large/streaming bodies |

The existing `/api/clone` and `/api/clone/pull` route handlers stay
where they are because they spawn `git` subprocesses. Everything new
should default to actions.

## Inventory

| Area | Action | Reads / Writes | Description |
|---|---|---|---|
| `users` | `createUser` | W | Insert a new user; rejects duplicate emails. |
| `users` | `listUsers` | R | All live users. |
| `users` | `softDeleteUser` | W | Soft-delete by id. |
| `accounts` | `createAccount` | W | Create an account owned by the current user. |
| `accounts` | `listAccountsForCurrentUser` | R | Live accounts owned by the current user. |
| `accounts` | `renameAccount` | W | Rename an account. |
| `logins` | `createEmailPasswordLogin` | W | bcrypt the plaintext, then insert. Rejects `(account, email)` duplicates. |
| `logins` | `verifyEmailPasswordLogin` | R + W | Verify; on success, stamp `lastLoginAt`. |
| `config` | `getCurrentAccountConfig` | R | Read or seed the current account's config. |
| `config` | `updateCurrentAccountConfig` | W | Replace the config body. |
| `config` | `resetCurrentAccountConfig` | W | Reset to factory defaults. |

## Adding a new action

1. Pick (or create) the right area folder under `actions/`.
2. Create one file per action. Name the file after the verb (e.g.
   `archiveAccount.ts`).
3. Write the file in the contract shape above.
4. Add a one-line entry to the area's `README.md`.
5. Add it to the inventory table in this doc.
6. Add a (small) test for the validation path if the schema is non-trivial.
