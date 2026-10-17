# ==============================================================================
# PublicHealthSentinel — Phase 8B.3 Frontend Dockerfile
#
# Production multi-stage build:
# 1. Builder: Node.js 22 Alpine installing dependencies via npm ci & compiling Vite SPA
# 2. Runner: Lightweight Nginx Alpine running as unprivileged user 'nginx'
# ==============================================================================

# --- Stage 1: Build production static bundle ---
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies deterministically from lockfile
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source and build production bundle
COPY . ./
RUN npm run build

# --- Stage 2: Production Nginx Server ---
FROM nginx:alpine AS runner

# Prepare unprivileged temporary storage locations and static assets directory
RUN mkdir -p /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp /usr/share/nginx/html && \
    chown -R nginx:nginx /tmp /usr/share/nginx/html /var/cache/nginx /var/log/nginx

# Copy customized Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy compiled production assets from builder stage
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

# Switch to unprivileged nginx user (UID 101)
USER nginx

EXPOSE 8080

# Native healthcheck using built-in Alpine wget
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
