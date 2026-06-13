# @router/client-ts

TypeScript **@grpc/grpc-js** client for `pod_manager.v1.PodManagerService` (port **8804**).

## Install

```bash
cd router.svc/client_ts
npm install
npm run proto:gen
npm run build
```

Proto generation uses **ts-proto** (`npm run proto:gen`). Regenerate when `../server/proto/pod_manager/v1/pool.proto` changes.

## Example

```typescript
import { PodManagerClient } from "@router/client-ts";

const pm = new PodManagerClient({ host: "localhost", port: 8804 });
try {
  const lease = await pm.acquireLease("alice");
  console.log(lease.podId, lease.podDns);
  await pm.releaseLease("alice");
} finally {
  pm.close();
}
```

## Parity with `client_py`

| Python | TypeScript |
|--------|------------|
| `PodManagerClient` | `PodManagerClient` |
| `PodManagerClientError` | `PodManagerClientError` |
| `LeaseResult` | `LeaseResult` |
| `PoolStatus` | `PoolStatus` |
| `async with` / `close()` | `close()` (sync) |

Request fields are validated with **Zod** before RPCs (see `src/validation/`).
