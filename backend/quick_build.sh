#!/bin/bash

# Quick Build Script for Backend - Handles common build issues

set -e

echo "🚀 Building Backend with Build Issue Workarounds..."

# Use a different approach - build in stages
echo "Step 1: Building base Python image..."
docker build -f Dockerfile.base -t rag-backend-base . 2>/dev/null || echo "Base build failed, continuing with direct build..."

echo "Step 2: Installing dependencies with fallback strategies..."

# Try to build with fallback for gRPC issues
docker build --no-cache -t rag-backend . 2>&1 | tee build.log

# Check if build succeeded
if [ $? -eq 0 ]; then
    echo "✅ Build successful!"

    # Test the image
    echo "Testing built image..."
    docker run --rm rag-backend python -c "import fastapi; print('FastAPI imported successfully')"

    echo "🎉 Backend build complete!"
    echo ""
    echo "Next steps:"
    echo "  • make up          # Start all services"
    echo "  • make init-db     # Initialize database"
    echo "  • make validate    # Run Phase 1 validation"

else
    echo "❌ Build failed. Checking for common issues..."

    # Check for gRPC issues
    if grep -q "grpcio" build.log; then
        echo "Found gRPC build issues. Creating simplified requirements..."

        # Create a simplified requirements file
        cat > requirements.simple.txt << EOF
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.23
alembic==1.13.1
psycopg2-binary==2.9.9

# Authentication & Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6

# Background Processing
celery==5.3.4
redis==5.0.1

# HTTP Client
httpx==0.25.2
aiohttp==3.9.1

# File Processing
python-magic==0.4.27
aiofiles==23.2.1
Pillow>=10.3.0

# Basic ML
scikit-learn==1.3.2
numpy==1.24.4

# Development
pytest==7.4.3
black==23.11.0
isort==5.12.0
EOF

        echo "Created requirements.simple.txt for easier installation"
        echo "Try: docker build -f Dockerfile.simple -t rag-backend-simple ."

    fi

    echo ""
    echo "Check build.log for detailed error information"
    echo ""
    echo "Alternative approaches:"
    echo "  1. Use development requirements: pip install -r requirements.dev.txt"
    echo "  2. Install packages manually to avoid compilation"
    echo "  3. Use pre-built wheels: pip install --prefer-binary"
fi

# Clean up
rm -f build.log