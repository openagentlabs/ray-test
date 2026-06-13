# router-client

Python **grpc.aio** client for `pod_manager.v1.PodManagerService` (port **8804**).

## Install

```bash
cd router.svc/client_py
uv sync --extra dev
bash tools/generate_protos.sh
uv pip install -e .
```

Proto generation needs **`grpcio-tools`** (included in the `dev` extra). Do not use bare `python` on the host unless that environment already has `grpc_tools` installed.

## Example

```python
import asyncio
from pod_manager_client import PodManagerClient

async def main() -> None:
    async with PodManagerClient(host="localhost", port=8804) as pm:
        lease = await pm.acquire_lease("alice")
        print(lease.pod_id, lease.pod_dns)
        await pm.release_lease("alice")

asyncio.run(main())
```
