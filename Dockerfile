# Stage 1: Build frontend
FROM node:20-slim AS frontend
WORKDIR /build
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

# Stage 2: Backend + bundled frontend
FROM python:3.12.8-slim

WORKDIR /app

COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/backend/ .

# Copy built frontend into backend static dir
COPY --from=frontend /build/dist /app/static

# Copy data files (norm cache + golden dataset)
COPY data/ /app/data

RUN adduser --disabled-password --gecos "" appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:50505/health')" || exit 1

EXPOSE 50505

ENV HOST=0.0.0.0
CMD ["python", "main.py"]
