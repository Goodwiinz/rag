# Quick Start Guide: Multimodal Enterprise RAG System

**Date**: 2025-10-07
**Target Audience**: Developers, DevOps, System Administrators

## Overview

This guide provides step-by-step instructions for setting up and running the Multimodal Enterprise RAG System in development and production environments.

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows with WSL2
- **RAM**: Minimum 16GB (32GB recommended)
- **CPU**: 4+ cores (8+ recommended)
- **GPU**: NVIDIA GPU with CUDA support (recommended for ML tasks)
- **Storage**: 50GB free space

### Software Requirements
- **Docker**: 20.10 or later
- **Docker Compose**: 2.0 or later
- **Python**: 3.11+ (for local development)
- **Node.js**: 18+ (for frontend development)
- **Git**: For version control

## Installation

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
```bash
git clone https://github.com/your-org/multimodal-rag-system.git
cd multimodal-rag-system
```

2. **Copy environment configuration**
```bash
cp .env.example .env
```

3. **Edit environment variables**
```bash
# .env file
# Database configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=your_qdrant_api_key

POSTGRES_URL=postgresql://postgres:postgres@postgres:5432/multimodal_rag
REDIS_URL=redis://redis:6379

# Application configuration
SECRET_KEY=your_secret_key_for_jwt
JWT_EXPIRE_HOURS=24

# External services
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

4. **Start services**
```bash
docker-compose up -d
```

5. **Wait for services to initialize**
```bash
docker-compose logs -f
```

6. **Verify all services are running**
```bash
docker-compose ps
```

### Option 2: Local Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/your-org/multimodal-rag-system.git
cd multimodal-rag-system
```

2. **Set up Python virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install backend dependencies**
```bash
cd backend
pip install -r requirements.txt
```

4. **Set up frontend dependencies**
```bash
cd frontend
npm install
```

5. **Set up databases**
```bash
# Start PostgreSQL, Neo4j, Qdrant, Redis
docker-compose up -d postgres neo4j qdrant redis

# Run database migrations
cd backend
python manage.py migrate

# Load initial data
python manage.py load_initial_data
```

## Initial Setup

### 1. Create Admin User

```bash
# Using Docker
docker-compose exec backend python manage.py createsuperuser

# Local development
cd backend
python manage.py createsuperuser
```

### 2. Create Organization

```bash
# Using the API
curl -X POST http://localhost:8000/api/v1/organizations \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Organization",
    "storage_tier": "free"
  }'
```

### 3. Download ML Models

```bash
# Download required models (one-time setup)
docker-compose exec backend python scripts/download_models.py

# Models downloaded:
# - Sentence transformers for embeddings
# - Whisper for audio transcription
# - YOLO for object detection
# - Tesseract for OCR
```

## Basic Usage

### 1. Access the Application

- **Web Interface**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474
- **Qdrant Dashboard**: http://localhost:6333

### 2. User Registration

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### 3. User Login

```bash
# Login and get access token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123"
  }'
```

### 4. Upload a Document

```bash
# Upload a PDF file
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "description=Annual report 2023"
```

### 5. Search Documents

```bash
# Search across all documents
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "limit": 10
  }'
```

## Development Workflow

### Backend Development

1. **Start backend server**
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. **Run tests**
```bash
cd backend
pytest tests/ -v
```

3. **Run specific test categories**
```bash
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/
```

### Frontend Development

1. **Start frontend development server**
```bash
cd frontend
npm start
```

2. **Run frontend tests**
```bash
cd frontend
npm test
```

### Database Management

1. **Create migrations**
```bash
cd backend
python manage.py makemigrations
```

2. **Apply migrations**
```bash
python manage.py migrate
```

3. **Database shell**
```bash
python manage.py dbshell
```

## Production Deployment

### 1. Environment Configuration

```bash
# Production environment variables
export ENVIRONMENT=production
export SECRET_KEY=your_production_secret_key
export DATABASE_URL=postgresql://user:pass@prod-db:5432/multimodal_rag
export REDIS_URL=redis://prod-redis:6379
export NEO4J_URI=bolt://prod-neo4j:7687
export QDRANT_URL=http://prod-qdrant:6333
```

### 2. Docker Deployment

```bash
# Build and start production services
docker-compose -f docker-compose.prod.yml up -d

# Monitor logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 3. SSL/TLS Configuration

```bash
# Generate SSL certificates
certbot certonly --standalone -d your-domain.com

# Configure nginx with SSL
cp ssl/* /etc/nginx/ssl/
nginx -t && nginx -s reload
```

### 4. Backup Strategy

```bash
# Database backups
docker-compose exec postgres pg_dump -U postgres multimodal_rag > backup.sql

# Neo4j backups
docker-compose exec neo4j cypher-shell "CALL apoc.export.csv.all('backup.csv', {})"

# File storage backups
rsync -av /path/to/storage/ /backup/location/
```

## Monitoring and Maintenance

### 1. Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Database health
docker-compose exec postgres pg_isready

# Neo4j health
curl http://localhost:7474/db/data/
```

### 2. Performance Monitoring

- **Application Metrics**: http://localhost:8000/metrics
- **Grafana Dashboard**: http://localhost:3000
- **Prometheus**: http://localhost:9090

### 3. Log Management

```bash
# View application logs
docker-compose logs -f backend

# View database logs
docker-compose logs -f postgres

# View search logs
docker-compose logs -f qdrant
```

### 4. Common Maintenance Tasks

```bash
# Cleanup old search queries
docker-compose exec backend python manage.py cleanup_old_queries --days=30

# Rebuild search indexes
docker-compose exec backend python manage.py rebuild_indexes

# Update ML models
docker-compose exec backend python manage.py update_models
```

## Troubleshooting

### Common Issues

1. **Services not starting**
```bash
# Check container status
docker-compose ps

# View specific service logs
docker-compose logs service_name
```

2. **Database connection issues**
```bash
# Test database connectivity
docker-compose exec postgres psql -U postgres -d multimodal_rag

# Check database logs
docker-compose logs postgres
```

3. **ML model loading issues**
```bash
# Check available disk space
df -h

# Check memory usage
free -h

# Re-download models
docker-compose exec backend python scripts/download_models.py --force
```

4. **Performance issues**
```bash
# Monitor resource usage
docker-compose stats

# Check database performance
docker-compose exec postgres top
```

### Performance Tuning

1. **Database optimization**
```sql
-- Add indexes for frequently queried fields
CREATE INDEX CONCURRENTLY idx_documents_organization_id ON documents(organization_id);
CREATE INDEX CONCURRENTLY idx_documents_processing_status ON documents(processing_status);
```

2. **Vector search optimization**
```python
# Adjust vector search parameters
vector_search_config = {
    "ef_search": 100,  # Increase for better recall
    "hnsw_ef_construction": 200,
    "hnsw_m": 16
}
```

3. **Caching optimization**
```python
# Configure Redis caching
CACHE_CONFIG = {
    "default_timeout": 300,
    "key_prefix": "multimodal_rag:",
    "max_memory": "1gb"
}
```

## Security Considerations

### 1. Environment Security

- Never commit `.env` files to version control
- Use strong, unique passwords for all services
- Rotate API keys and secrets regularly
- Enable SSL/TLS in production

### 2. Network Security

- Use firewall rules to restrict access
- Enable VPN for administrative access
- Monitor for suspicious activity
- Implement rate limiting

### 3. Data Security

- Encrypt sensitive data at rest
- Enable database encryption
- Regular security audits
- Data backup and recovery procedures

## Support and Resources

### Documentation
- **API Documentation**: http://localhost:8000/docs
- **Developer Guide**: `/docs/development.md`
- **Deployment Guide**: `/docs/deployment.md`

### Community Support
- **GitHub Issues**: https://github.com/your-org/multimodal-rag-system/issues
- **Discord Channel**: https://discord.gg/multimodal-rag
- **Stack Overflow**: Use tag [multimodal-rag]

### Enterprise Support
- Email: enterprise@multimodal-rag.com
- SLA: 24/7 support available
- On-premise deployment support
- Custom development services

## Next Steps

1. **Complete Setup**: Follow all steps to get the system running
2. **Upload Test Data**: Add sample documents to test functionality
3. **Configure Search**: Fine-tune search parameters for your use case
4. **Set Up Monitoring**: Configure alerts and dashboards
5. **Plan Production**: Prepare for production deployment

For more detailed information, refer to the full documentation in the `/docs` directory.