# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /src

# Keep the same repository layout used by the Vercel build: the frontend
# postbuild step publishes the root llms.txt and ai-index.json files.
COPY frontend/package*.json ./frontend/
COPY llms.txt ai-index.json ./
COPY docker/build-data/ ./web/data/
COPY frontend/static/data/ ./web/data/

# Install dependencies
RUN cd frontend && npm ci

# Copy frontend source
COPY frontend/ ./frontend/

# Build the frontend (outputs to ../web)
RUN cd frontend && RAIDAR_ALLOW_EMPTY_REPORT_DATA=true npm run build

# Stage 2: Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cron \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser runtime used by the LessWrong cookie bypass
RUN python -m playwright install --with-deps chromium

# Copy application code
COPY agents/ ./agents/
COPY generators/ ./generators/
COPY pipeline_support/ ./pipeline_support/
COPY scripts/ ./scripts/
COPY assets/ ./assets/
COPY frontend/static/ ./frontend/static/
COPY config/ ./config-defaults/
COPY run_pipeline.py .
COPY report_schema.py .
COPY llms.txt ai-index.json ./
COPY entrypoint.sh .

# Create necessary directories
RUN mkdir -p /app/config /app/data /app/web /app/logs

# Copy built frontend from stage 1
COPY --from=frontend-builder /src/web ./web/

# Make scripts executable
RUN chmod +x run_pipeline.py entrypoint.sh

# Configure nginx
COPY nginx.conf /etc/nginx/sites-available/default

# Expose web port
EXPOSE 80

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
