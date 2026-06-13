# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# ---------------------------------------------------------------------------
# Vite build-time environment variables.
# All VITE_* values are baked into the static JS bundle by `npm run build`
# (import.meta.env.VITE_*).  They are non-sensitive — already public once
# the bundle is served.
#
# Injected by docker-build-matrix.sh via --build-arg, which reads them from
# AWS Secrets Manager (midas-{env}-us-east-1/frontend) before the build.
# Defaults are empty so a local `docker build` without args still produces a
# valid (auth-unconfigured) image rather than failing.
# ---------------------------------------------------------------------------
ARG VITE_BASE_URL=""
ARG VITE_COGNITO_DOMAIN=""
ARG VITE_COGNITO_CLIENT_ID=""
ARG VITE_COGNITO_REDIRECT_URI=""
ARG VITE_COGNITO_LOGOUT_REDIRECT_URI=""
ARG VITE_COGNITO_SCOPES="openid email profile"

# Promote ARGs to ENV so Vite can read them via process.env at build time.
ENV VITE_BASE_URL=$VITE_BASE_URL \
    VITE_COGNITO_DOMAIN=$VITE_COGNITO_DOMAIN \
    VITE_COGNITO_CLIENT_ID=$VITE_COGNITO_CLIENT_ID \
    VITE_COGNITO_REDIRECT_URI=$VITE_COGNITO_REDIRECT_URI \
    VITE_COGNITO_LOGOUT_REDIRECT_URI=$VITE_COGNITO_LOGOUT_REDIRECT_URI \
    VITE_COGNITO_SCOPES=$VITE_COGNITO_SCOPES

# Copy package files
COPY package*.json ./

# Install dependencies required for build (includes devDependencies like vite)
RUN npm ci

# Copy source code
COPY . .

# Build the application — Vite bakes VITE_* ENV vars into the JS bundle here.
RUN npm run build

# Development stage
FROM node:20-alpine AS dev

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# Production stage - Node serves static assets and proxies /api (no nginx)
FROM node:20-alpine

WORKDIR /srv
ENV NODE_ENV=production \
    PORT=8080 \
    BACKEND_UPSTREAM=http://midas-api-backend-svc.midas-apps.svc.cluster.local:8000

RUN apk add --no-cache curl

COPY prod-runtime-package.json ./package.json
RUN npm install --omit=dev && rm -f package.json

COPY production-server.cjs ./
COPY --from=builder /app/dist ./dist

RUN chown -R node:node /srv

EXPOSE 8080
USER node
CMD ["node", "/srv/production-server.cjs"]
