# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build FastAPI Backend
FROM python:3.13-slim
WORKDIR /app

# Install system dependencies if needed (e.g., curl, git)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv to manage python virtualenv or packages
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Sync Python packages
COPY pyproject.toml requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Copy application source
COPY backend/ ./backend/
COPY tests/ ./tests/
COPY README.md ./

# Copy built frontend assets to the directory FastAPI will serve
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose the API Port
EXPOSE 8000

# Set environment variables defaults
ENV PORT=8000
ENV HOST=0.0.0.0

CMD ["python", "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
