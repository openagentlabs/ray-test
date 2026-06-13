# Docker_K8S_Saiyam_Manual

## 1. Purpose
This guide documents the exact Docker + Kubernetes setup for this repository:

- Local production-like run (`docker-compose.yml`)
- Local development run with live reload (`docker-compose.dev.yml` override)
- Image push to ECR
- Deployment to EKS
- Secrets handling for local and AWS

---

## 2. File Map

- `docker-compose.yml`: Production-like local stack
- `docker-compose.dev.yml`: Dev overrides (hot reload, bind mounts)
- `backend/Dockerfile`: Python backend image (Gunicorn in production)
- `frontend/Dockerfile`: Frontend build + nginx runtime
- `frontend/nginx.conf`: API reverse proxy + `/health` passthrough
- `k8s/backend-deployment.yaml`: Backend Deployment + Service
- `k8s/frontend-deployment.yaml`: Frontend Deployment + Service
- `k8s/backend-secret.template.yaml`: Kubernetes secret template
- `k8s/ingress.yaml`: ALB ingress
- `ECR_EKS_DEPLOY.md`: Existing quick deploy notes

---

## 3. Ports In Use

### Local Production-like (`docker-compose.yml`)
- Backend container: `8000`
- Backend host mapping: `8000:8000`
- Frontend nginx container: `80`
- Frontend host mapping: `3000:80`

Use:
- Frontend UI: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`

### Local Dev (`docker-compose.yml + docker-compose.dev.yml`)
- Backend: `8000` (uvicorn reload)
- Frontend dev server: `5173` (Vite)
- Frontend host mapping in dev override: `5173:5173`

Use:
- Frontend UI: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`

### EKS
- Backend Service: port `8000` (ClusterIP)
- Frontend Service: port `80` (ClusterIP)
- External traffic enters via Ingress to frontend.

---

## 4. Environment Variables

## 4.1 Backend runtime env (from `backend/.env`)
Primary keys used by backend:

- `ENDPOINT`
- `API_KEY`
- `MODEL`
- `EMBEDDING_MODEL`
- `EMBEDDING_ENDPOINT`
- `API_KEY_EMBEDDING`
- `AZURE_KG_ENDPOINT`
- `KG_MODEL`

Optional backend env supported by config/code:
- `DATABASE_PATH`
- `DATABASE_CLEANUP_DAYS`
- `LOG_LEVEL`
- `LOG_FILE`
- `ENABLE_CONSOLE_LOGGING`
- `WEB_CONCURRENCY` (Gunicorn worker count; EKS Helm chart [`midas-api-backend-svc`](deploy/ecs-app/helm/midas-api-backend-svc/values.yaml) defaults `webConcurrency` to 1, override in values when using Postgres and you want more workers)
- `GUNICORN_TIMEOUT` (Gunicorn timeout seconds)

Where loaded:
- `docker-compose.yml` backend service uses `env_file: ./backend/.env`
- For EKS, these should come from Kubernetes Secret (ideally synced from AWS Secrets Manager).

## 4.2 Frontend env
In dev override:
- `VITE_BASE_URL=http://localhost:8000`
- `VITE_DEV_PROXY_TARGET=http://backend:8000`

In production-like compose:
- Frontend container env uses `BACKEND_UPSTREAM=http://backend:8000` for nginx runtime template.

---

## 5. Volumes and Persistence

In `docker-compose.yml`:

- `./backend/logs:/app/logs` (host bind for logs)
- `backend-uploads:/app/uploads` (named volume for uploaded datasets + metadata)

Why uploads volume matters:
- Backend now persists dataset metadata sidecar files in `/app/uploads`
- Prevents dataset-not-found issues across Gunicorn workers/restarts

---

## 6. Busybox Service (What and Why)

Service: `backend-volume-init`

- Image: `busybox:1.36`
- Command: `mkdir -p /uploads && chmod -R 0777 /uploads`
- Purpose: initialize the named uploads volume with write permissions before backend starts

Why needed:
- Backend runs as non-root user (`app`) inside container
- Fresh Docker named volumes are often root-owned
- Without init, backend upload can fail with:
  - `Permission denied: 'uploads/<dataset_id>_file.csv'`

It runs once and exits (`restart: "no"`). Backend depends on its successful completion.

---

## 7. Production-like vs Dev Containers

## 7.1 Production-like mode
Source:
- `docker-compose.yml`

Behavior:
- Backend runs Gunicorn:
  - `gunicorn main:app -k uvicorn.workers.UvicornWorker ...`
- Frontend runs nginx serving built static assets
- No live reload
- Closer to AWS runtime behavior

## 7.2 Dev mode
Source:
- base `docker-compose.yml` + override `docker-compose.dev.yml`

Behavior:
- Backend command overridden to:
  - `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Backend source bind-mounted (`./backend:/app`)
- Frontend runs Vite dev server on 5173
- Frontend source bind-mounted (`./frontend:/app`)
- Fast iteration + HMR/reload

---

## 8. Run Commands

## 8.1 Production-like local
Build and start:
```bash
docker compose build backend frontend
docker compose up -d backend frontend
```

Stop:
```bash
docker compose down
```

With logs:
```bash
docker compose logs -f --tail=200 backend frontend
```

## 8.2 Development local
Build and start:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build backend frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d backend frontend
```

Stop:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Logs:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f --tail=200 backend frontend
```

---

## 9. Where to Change Ports/URLs

### Change frontend host port (production-like)
- File: `docker-compose.yml`
- Section: `frontend -> ports`
- Default: `"3000:80"`

### Change backend host port
- File: `docker-compose.yml`
- Section: `backend -> ports`
- Default: `"8000:8000"`

### Change dev frontend port
- File: `docker-compose.dev.yml`
- Section:
  - `frontend -> command` (`--port 5173`)
  - `frontend -> ports` (`"5173:5173"`)

### Change frontend-to-backend upstream (prod-like nginx)
- File: `docker-compose.yml`
- Env: `BACKEND_UPSTREAM=http://backend:8000`
- Used by nginx template at runtime

### Change dev proxy target
- File: `docker-compose.dev.yml`
- Env: `VITE_DEV_PROXY_TARGET=http://backend:8000`

---

## 10. AWS ECR + EKS + Secrets Manager

## 10.1 Recommended naming

### ECR repositories
- `midas-backend`
- `midas-frontend`

### EKS Kubernetes secret
- `midas-backend-secrets` (already used in `k8s/backend-deployment.yaml`)

### AWS Secrets Manager secret (recommended)
Use one secret per app/env, for example:
- `midas/prod/backend`
- `midas/dev/backend`

Store JSON keys matching backend env variable names:
- `ENDPOINT`
- `API_KEY`
- `MODEL`
- `EMBEDDING_MODEL`
- `EMBEDDING_ENDPOINT`
- `API_KEY_EMBEDDING`
- `AZURE_KG_ENDPOINT`
- `KG_MODEL`

## 10.2 Flow

1. Build local images
```bash
docker compose build backend frontend
```

2. Tag for ECR
```bash
AWS_ACCOUNT_ID=<account-id>
AWS_REGION=<region>
TAG=<release-tag>

docker tag bu-analytics-gen-ai-midas-backend:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-backend:${TAG}
docker tag bu-analytics-gen-ai-midas-frontend:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-frontend:${TAG}
```

3. Push to ECR
```bash
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-backend:${TAG}
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-frontend:${TAG}
```

4. Update K8s manifests image fields
- `k8s/backend-deployment.yaml`
- `k8s/frontend-deployment.yaml`

5. Create/update backend secret in Kubernetes
- Start from `k8s/backend-secret.template.yaml`
- Prefer syncing values from AWS Secrets Manager into this K8s secret (via External Secrets Operator or CI pipeline).

6. Apply manifests
```bash
kubectl apply -f k8s/backend-secret.template.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

---

## 11. Troubleshooting Quick Checks

### Upload permission error in production compose
Symptom:
- `Permission denied: uploads/...csv`

Fix:
- Ensure `backend-volume-init` ran and succeeded:
```bash
docker compose run --rm backend-volume-init
docker compose up -d backend frontend
```

### Dataset not found (404) after upload
Likely old/stale dataset ID or pre-fix uploads.

Fix:
- Re-upload dataset once after backend restart
- Check backend logs:
```bash
docker compose logs -f --tail=200 backend
```

### Frontend cannot reach backend in dev
Check:
- `VITE_BASE_URL`
- `VITE_DEV_PROXY_TARGET`
- backend health at `http://localhost:8000/health`

---

## 12. Security Notes

- Never bake `.env` into images.
- Keep `backend/.env` local only for Docker Desktop.
- In AWS, inject secrets at runtime from Secrets Manager -> Kubernetes Secret -> env vars.
- Keep `.env.backup` as template only.

