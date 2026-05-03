FROM node:20-alpine AS deps
WORKDIR /app
COPY alembic-labs-frontend/package.json alembic-labs-frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY alembic-labs-frontend/ .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_LAB_3D_URL
ENV NEXT_PUBLIC_LAB_3D_URL=$NEXT_PUBLIC_LAB_3D_URL
ENV NEXT_TELEMETRY_DISABLED=1
# Mol* (Mol-Star) is a 4.8MB UMD bundle; serving it from /public and
# loading via <Script> sidesteps webpack ESM-interop and lets the
# global `molstar` object initialise reliably across browsers.
RUN cp node_modules/molstar/build/viewer/molstar.js public/molstar.js && \
    cp node_modules/molstar/build/viewer/molstar.css public/molstar.css
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
