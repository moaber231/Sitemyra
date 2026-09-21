FROM node:22-alpine AS development

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
EXPOSE 3000

# ---------------------------------------------------------------------------
# Production build (standalone output, see next.config.ts).
# Target `production` serves the prebuilt standalone server — no dev server,
# no source mounts, no devDependencies at runtime.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app

# NEXT_PUBLIC_* values are inlined at build time — pass via --build-arg
# (compose does this from BACKEND_PUBLIC_URL; see docker-compose.prod.yml).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-alpine AS production

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000 \
    HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
