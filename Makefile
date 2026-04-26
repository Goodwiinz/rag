# Multimodal RAG System - Makefile

.PHONY: help build up down clean test lint format init-db reset-db logs shell

# Default target
help:
	@echo "Multimodal RAG System - Development Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  build       Build all Docker images"
	@echo "  up          Start all services"
	@echo "  down        Stop all services"
	@echo "  clean       Clean up Docker containers and images"
	@echo ""
	@echo "Database Commands:"
	@echo "  init-db     Initialize database with default data"
	@echo "  reset-db    Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Development Commands:"
	@echo "  dev         Start development environment"
	@echo "  test        Run tests"
	@echo "  lint        Run linting"
	@echo "  format      Format code"
	@echo ""
	@echo "Utility Commands:"
	@echo "  logs        Show logs for all services"
	@echo "  shell       Open shell in backend container"
	@echo "  validate    Run Phase 1 validation"
	@echo ""

# Setup Commands
build:
	@echo "Building Docker images..."
	docker-compose build

up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services are starting up..."
	@sleep 10
	@echo "Services should be ready. Check with: make logs"

down:
	@echo "Stopping all services..."
	docker-compose down

clean:
	@echo "Cleaning up Docker containers and images..."
	docker-compose down -v --remove-orphans
	docker system prune -f

# Database Commands
init-db:
	@echo "Initializing database..."
	docker-compose exec backend python src/core/init_db.py init

reset-db:
	@echo "Resetting database..."
	@read -p "This will delete all data. Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker-compose exec backend python src/core/init_db.py reset; \
	else \
		echo "Database reset cancelled."; \
	fi

# Development Commands
dev: up
	@echo "Starting development environment..."
	@echo "Backend API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"
	@echo "Frontend: http://localhost:3000"
	@echo "Neo4j Browser: http://localhost:7474"
	@echo "Qdrant Dashboard: http://localhost:6333/dashboard"

test:
	@echo "Running tests..."
	docker-compose exec backend python -m pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	@echo "Running linting..."
	docker-compose exec backend flake8 src/ tests/
	docker-compose exec backend mypy src/

format:
	@echo "Formatting code..."
	docker-compose exec backend black src/ tests/
	docker-compose exec backend isort src/ tests/

# Utility Commands
logs:
	docker-compose logs -f

shell:
	docker-compose exec backend bash

validate:
	@echo "Running Phase 1 validation..."
	docker-compose exec backend python validate_phase1.py

# Individual Services
api:
	@echo "Starting only API server..."
	docker-compose up -d postgres redis neo4j qdrant backend

worker:
	@echo "Starting only Celery worker..."
	docker-compose up -d postgres redis neo4j qdrant celery-worker

beat:
	@echo "Starting only Celery beat..."
	docker-compose up -d postgres redis celery-beat

# Production Commands
prod-build:
	@echo "Building for production..."
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-up:
	@echo "Starting production environment..."
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Monitoring Commands
monitoring:
	@echo "Starting monitoring stack..."
	docker-compose --profile monitoring up -d
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3001 (admin/admin)"

# Quick Development Setup
quick-start: build dev init-db
	@echo ""
	@echo "🚀 Quick start complete!"
	@echo ""
	@echo "Services available:"
	@echo "  • API Server: http://localhost:8000"
	@echo "  • API Docs: http://localhost:8000/docs"
	@echo "  • Frontend: http://localhost:3000"
	@echo "  • Neo4j: http://localhost:7474 (neo4j/neo4jpassword)"
	@echo "  • Qdrant: http://localhost:6333"
	@echo ""
	@echo "Useful commands:"
	@echo "  • make logs     - View service logs"
	@echo "  • make test     - Run tests"
	@echo "  • make validate - Run validation"
	@echo "  • make shell    - Open shell in container"
	@echo ""