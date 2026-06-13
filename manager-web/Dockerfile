FROM node:22-bookworm AS builder
WORKDIR /app

COPY manager-web/package.json manager-web/package-lock.json ./manager-web/
WORKDIR /app/manager-web
RUN npm ci --ignore-scripts

COPY manager-web/ ./
RUN npm run build:fast

FROM node:22-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
  PORT=8811 \
  HOSTNAME=0.0.0.0

# Official node image ships `node` user (uid/gid 1000) — matches Ray and Helm sharedMounts.
COPY --from=builder /app/manager-web/public ./public
COPY --from=builder --chown=node:node /app/manager-web/.next/standalone ./
COPY --from=builder --chown=node:node /app/manager-web/.next/static ./.next/static

USER node
EXPOSE 8811

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8811/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
