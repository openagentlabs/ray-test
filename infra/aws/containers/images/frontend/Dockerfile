# DEPRECATED — use frontend/Dockerfile. Prefer: make build-dockers
#
# Legacy path (build from repository root):
#   docker build -f infra/containers/images/frontend/Dockerfile -t arb-frontend:local .

FROM node:22-bookworm AS grpc_clients
WORKDIR /repo

COPY document-storage.svc/server/proto ./document-storage.svc/server/proto
COPY arch.diagram.agent.svc/server/proto ./arch.diagram.agent.svc/server/proto

COPY general.ai.agent.svc/client/package.json general.ai.agent.svc/client/package-lock.json ./general.ai.agent.svc/client/
COPY notification.svc/client/package.json notification.svc/client/package-lock.json ./notification.svc/client/
COPY solutions.svc/client/package.json solutions.svc/client/package-lock.json ./solutions.svc/client/
COPY storage.svc/client/package.json storage.svc/client/package-lock.json ./storage.svc/client/
COPY collaboration.svc/client/package.json collaboration.svc/client/package-lock.json ./collaboration.svc/client/
COPY document-storage.svc/client/package.json document-storage.svc/client/package-lock.json ./document-storage.svc/client/
COPY arch.diagram.agent.svc/client/package.json arch.diagram.agent.svc/client/package-lock.json ./arch.diagram.agent.svc/client/

RUN cd /repo/general.ai.agent.svc/client && npm ci --ignore-scripts \
  && cd /repo/notification.svc/client && npm ci --ignore-scripts \
  && cd /repo/solutions.svc/client && npm ci --ignore-scripts \
  && cd /repo/storage.svc/client && npm ci --ignore-scripts \
  && cd /repo/collaboration.svc/client && npm ci --ignore-scripts \
  && cd /repo/document-storage.svc/client && npm ci --ignore-scripts \
  && cd /repo/arch.diagram.agent.svc/client && npm ci --ignore-scripts

COPY general.ai.agent.svc/client ./general.ai.agent.svc/client
COPY notification.svc/client ./notification.svc/client
COPY solutions.svc/client ./solutions.svc/client
COPY storage.svc/client ./storage.svc/client
COPY collaboration.svc/client ./collaboration.svc/client
COPY document-storage.svc/client ./document-storage.svc/client
COPY arch.diagram.agent.svc/client ./arch.diagram.agent.svc/client

RUN cd /repo/general.ai.agent.svc/client && npm run build \
  && cd /repo/notification.svc/client && npm run build \
  && cd /repo/solutions.svc/client && npm run build \
  && cd /repo/storage.svc/client && npm run build \
  && cd /repo/collaboration.svc/client && npm run build \
  && cd /repo/document-storage.svc/client && npx tsc -p tsconfig.json \
  && cd /repo/arch.diagram.agent.svc/client && npx tsc -p tsconfig.json

FROM node:22-bookworm AS builder
WORKDIR /app

COPY --from=grpc_clients /repo/general.ai.agent.svc/client ./general.ai.agent.svc/client
COPY --from=grpc_clients /repo/notification.svc/client ./notification.svc/client
COPY --from=grpc_clients /repo/solutions.svc/client ./solutions.svc/client
COPY --from=grpc_clients /repo/storage.svc/client ./storage.svc/client
COPY --from=grpc_clients /repo/collaboration.svc/client ./collaboration.svc/client
COPY --from=grpc_clients /repo/document-storage.svc/client ./document-storage.svc/client
COPY --from=grpc_clients /repo/arch.diagram.agent.svc/client ./arch.diagram.agent.svc/client

COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /app/frontend
RUN npm ci --ignore-scripts

COPY frontend/ ./
RUN npm run build -- --webpack

FROM node:22-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
  PORT=8802 \
  HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 --ingroup nodejs --no-create-home nextjs

COPY --from=builder /app/frontend/public ./frontend/public
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./frontend/.next/static

USER nextjs
EXPOSE 8802

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8802/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "frontend/server.js"]
