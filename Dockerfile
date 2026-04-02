# Multi-stage Dockerfile: build Vite frontend, then run FastAPI backend serving static files

### Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app
# Copy the whole repo so build tools and configs (e.g. tsconfig.app.json) are available
COPY . .
RUN npm ci --silent
RUN npm run build

### Run Python app
FROM python:3.11-slim
WORKDIR /app

# system deps (scikit-learn may require build tools on some platforms)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy built frontend
COPY --from=frontend-build /app/dist ./dist

# Copy Python code and requirements (include model.joblib if present)
COPY requirements.txt ./
# Copy all top-level Python files so backend modules (policy_management.py, etc.) are available
COPY ./*.py ./
COPY model.joblib* ./

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT 10000
EXPOSE 10000

# Use a shell form CMD so environment variable expansion works at runtime on Render.
# Default to 10000 if PORT is not set.
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-10000}"]
