FROM node:22-bookworm AS builder
WORKDIR /app

COPY iam.svc/http-auth-client/package.json iam.svc/http-auth-client/package-lock.json ./iam.svc/http-auth-client/
WORKDIR /app/iam.svc/http-auth-client
RUN npm ci --ignore-scripts
COPY iam.svc/http-auth-client/ ./
RUN npm run build

WORKDIR /app
COPY web-app/package.json web-app/package-lock.json ./web-app/
COPY web-app/ ./web-app/
WORKDIR /app/web-app
RUN npm ci --ignore-scripts
RUN rm -rf node_modules/@arb/http-auth-client && cp -r ../iam.svc/http-auth-client node_modules/@arb/http-auth-client
RUN npm run build:fast

FROM node:22-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
  PORT=8811 \
  HOSTNAME=0.0.0.0

# Official node image ships `node` user (uid/gid 1000) — matches Ray and Helm sharedMounts.
COPY --from=builder /app/web-app/public ./public
COPY --from=builder --chown=node:node /app/web-app/.next/standalone ./
COPY --from=builder --chown=node:node /app/web-app/.next/static ./.next/static

USER node
EXPOSE 8811

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8811/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
