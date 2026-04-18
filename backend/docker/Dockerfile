# Multi-stage production-ready Dockerfile for the Multimodal RAG System Backend
# Stage 1: Python base with system dependencies
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Stage 2: Dependencies builder
FROM base AS dependencies

WORKDIR /app

# Copy requirements files
COPY backend/requirements.txt backend/requirements-minimal.txt ./

# Install Python dependencies while preserving pkg_resources for pybtex.
RUN pip install --upgrade pip wheel "setuptools<72" && \
    pip install -r requirements.txt && \
    pip install -r requirements-minimal.txt && \
    pip install "setuptools<72" && \
    python -c "import pkg_resources"

# Stage 3: Development
FROM base AS development

WORKDIR /app

# Copy Python dependencies
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Install additional development dependencies
COPY backend/requirements.dev.txt ./
RUN pip install -r requirements.dev.txt

# Copy source code
COPY backend/ ./

# Set permissions
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run development server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 4: Production
FROM base AS production

WORKDIR /app

# Copy Python dependencies only
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy source code
COPY backend/ ./

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Create necessary directories
RUN mkdir -p uploads logs && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run production server with Gunicorn
CMD ["gunicorn", "src.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]

# Stage 5: Celery Worker
FROM base AS worker

WORKDIR /app

# Copy Python dependencies
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy source code
COPY backend/ ./

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Create necessary directories
RUN mkdir -p uploads logs && \
    chown -R appuser:appuser /app

USER appuser

# Run Celery worker
CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
