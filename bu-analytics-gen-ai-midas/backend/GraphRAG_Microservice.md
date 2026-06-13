## GraphRAG Microservice (Local + Docker + Cloud)

This project supports both modes:
- Fully local (no Docker) using `start_graphrag_service.ps1`
- Containerized GraphRAG service for Docker Desktop, Azure, or AWS

### 1. Local (No Docker)

Run from `backend/`:

```powershell
.\start_graphrag_service.ps1
```

Optional flags:

```powershell
.\start_graphrag_service.ps1 -Python312Path "C:\Path\To\python.exe" -Port 8001
.\start_graphrag_service.ps1 -SkipInstall
```

The script now auto-detects Python 3.12 candidates and also honors `GRAPHRAG_PYTHON_PATH`.

### 2. Docker Desktop (Local)

From `backend/`:

```powershell
docker compose --env-file .env -f docker-compose.graphrag.yml up -d --build
```

Check health:

```powershell
curl http://localhost:8001/health
```

Stop:

```powershell
docker compose -f docker-compose.graphrag.yml down
```

### 3. Backend Integration (important)

Your backend can call GraphRAG at any URL via:

```env
GRAPHRAG_SERVICE_URL=http://localhost:8001
```

- If `GRAPHRAG_SERVICE_URL` points to localhost, backend auto-start can still run local subprocess mode.
- If `GRAPHRAG_SERVICE_URL` points to a remote/container host (Azure/AWS/private DNS), backend will not auto-spawn local GraphRAG process.
- You can override behavior explicitly with:

```env
GRAPHRAG_AUTOSTART=true
# or
GRAPHRAG_AUTOSTART=false
```

### 4. Azure Web App / AWS Container Service

Build/push image using `backend/Dockerfile.graphrag`, then deploy as container service.

Required runtime env vars in Azure/AWS service config:

```env
GRAPHRAG_API_KEY=<required>
GRAPHRAG_SERVICE_PORT=8001
AZURE_OPENAI_API_KEY=<if used>
AZURE_OPENAI_ENDPOINT=<if used>
AZURE_OPENAI_DEPLOYMENT_NAME=<if used>
```

Then set your main backend app variable to consume deployed GraphRAG URL:

```env
GRAPHRAG_SERVICE_URL=https://<your-graphrag-service-url>
GRAPHRAG_AUTOSTART=false
```

### 5. Files Added for Containerization

- `backend/Dockerfile.graphrag`
- `backend/docker-compose.graphrag.yml`
- `backend/.dockerignore`

### 6. Notes

- `knowledge_repo_kg` must exist and contain built GraphRAG outputs.
- Docker compose mounts `knowledge_repo_kg`, `kg_logs`, and `kg_cache` as volumes for local persistence.
- Existing local non-Docker workflow remains supported.
