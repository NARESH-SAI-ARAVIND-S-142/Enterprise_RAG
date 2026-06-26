# ─── Stage 1: Build Next.js Frontend ──────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit

COPY frontend/ .

# Point frontend API calls to the same origin (nginx will proxy)
ENV NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_WS_URL=""

RUN npm run build


# ─── Stage 2: Production Runtime ──────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libmagic1 \
    poppler-utils \
    nginx \
    supervisor \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/

# Copy built frontend
COPY --from=frontend-builder /frontend/.next /frontend/.next
COPY --from=frontend-builder /frontend/public /frontend/public
COPY --from=frontend-builder /frontend/package.json /frontend/package.json
COPY --from=frontend-builder /frontend/node_modules /frontend/node_modules
COPY --from=frontend-builder /frontend/next.config.ts /frontend/next.config.ts

# Copy deployment configs
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/supervisord.conf /etc/supervisor/conf.d/documind.conf

# Create directories with correct permissions for HF Spaces
RUN mkdir -p /data/uploads /data/qdrant_storage /data/db && \
    chmod -R 777 /data && \
    mkdir -p /var/log/supervisor && \
    mkdir -p /var/run/nginx && \
    # Remove default nginx site
    rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# HF Spaces runs as user 1000, ensure permissions
RUN useradd -m -u 1000 user || true
RUN chown -R 1000:1000 /app /frontend /data /var/log /var/run/nginx /var/lib/nginx 2>/dev/null || true

EXPOSE 7860

# Start supervisor (manages nginx + backend + frontend)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/documind.conf", "-n"]
