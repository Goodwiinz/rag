FROM python:3.11-slim

# Set environment variables for better pip performance
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libmagic1 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libsndfile1 \
    libgl1 \
    libgtk-3-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install problematic packages first with specific flags
RUN pip install --no-cache-dir --prefer-binary grpcio==1.59.3 grpcio-tools==1.59.3 || \
    pip install --no-cache-dir --no-build-isolation grpcio==1.59.3 grpcio-tools==1.59.3 || \
    pip install --no-cache-dir grpcio grpcio-tools

# Install other heavy packages separately to isolate build issues
RUN pip install --no-cache-dir --prefer-binary torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu || \
    pip install --no-cache-dir torch torchvision torchaudio

RUN pip install --no-cache-dir --prefer-binary sentence-transformers || \
    pip install --no-cache-dir sentence-transformers

RUN pip install --no-cache-dir --prefer-binary transformers || \
    pip install --no-cache-dir transformers

RUN pip install --no-cache-dir --prefer-binary qdrant-client || \
    pip install --no-cache-dir qdrant-client

# Install remaining packages
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model with retry and fallback
RUN python -m spacy download en_core_web_sm || \
    (echo "Retrying spaCy download..." && \
     python -m spacy download en_core_web_sm --user) || \
    (echo "Installing spacy model manually..." && \
     pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz)

# Copy application code
COPY . .

# Create uploads directory with proper permissions
RUN mkdir -p /app/uploads/documents \
    /app/uploads/images \
    /app/uploads/audio \
    /app/uploads/video \
    /app/uploads/temp \
    /app/uploads/processed \
    && chmod 755 /app/uploads

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]