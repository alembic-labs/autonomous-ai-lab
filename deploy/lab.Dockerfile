FROM node:20-alpine AS builder
WORKDIR /app
COPY alembic-lab-3d/package.json alembic-lab-3d/package-lock.json ./
RUN npm ci
COPY alembic-lab-3d/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
