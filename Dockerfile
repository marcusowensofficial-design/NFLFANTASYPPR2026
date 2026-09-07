# Multi-stage Dockerfile to build both React Frontend & FastAPI Backend

# Stage 1: Build the Vite / React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install runtime and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code, reference data, and tests
COPY src/ ./src/
COPY data/ ./data/
COPY tests/ ./tests/
COPY pyproject.toml .

# Copy pre-built frontend from stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure SQLite data folder exists
RUN mkdir -p /app/data

# Default port is 8000 (Render will override $PORT dynamically)
ENV PORT=8000
EXPOSE 8000

CMD exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
