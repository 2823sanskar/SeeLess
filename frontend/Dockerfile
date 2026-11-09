# syntax=docker/dockerfile:1
# Multi-stage build for the SeeLess Next.js frontend

FROM node:20-alpine AS deps

WORKDIR /app

# Install dependencies only (layer cache)
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

FROM node:20-alpine AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/.env.example ./.env.example

# Ownership for non-root user
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["npm", "start"]