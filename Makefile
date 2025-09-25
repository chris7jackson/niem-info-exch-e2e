.PHONY: help build up down logs clean test benchmark seed

# Default target
help:
	@echo "NIEM Information Exchange - Make Commands"
	@echo "========================================"
	@echo ""
	@echo "Setup Commands:"
	@echo "  build     - Build all Docker images"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  seed      - Initialize databases and services"
	@echo ""
	@echo "Development Commands:"
	@echo "  logs      - View all service logs"
	@echo "  test      - Run tests"
	@echo "  clean     - Clean up containers and volumes"
	@echo ""
	@echo "Benchmarking:"
	@echo "  benchmark - Run performance benchmarks"
	@echo "  dataset   - Generate test dataset"
	@echo ""
	@echo "Monitoring:"
	@echo "  status    - Check service health"
	@echo "  reset     - Reset all data (destructive)"

# Build all services
build:
	@echo "Building Docker images..."
	docker compose build

# Start all services
up:
	@echo "Starting services..."
	docker compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 30
	@make status

# Stop all services
down:
	@echo "Stopping services..."
	docker compose down

# Initialize databases and services
seed:
	@echo "Seeding databases..."
	python3 scripts/seed_minio.py
	./scripts/seed_redis.sh
	@echo "Seeding completed!"

# View logs
logs:
	docker compose logs -f

# Check service health
status:
	@echo "Checking service health..."
	@echo ""
	@echo "API Service:"
	@curl -s http://localhost:8000/healthz | jq . || echo "❌ API not available"
	@echo ""
	@echo "CMF Service:"
	@curl -s http://localhost:8080/healthz | jq . || echo "❌ CMF not available"
	@echo ""
	@echo "Ingestor Service:"
	@curl -s http://localhost:7000/healthz | jq . || echo "❌ Ingestor not available"
	@echo ""
	@echo "UI Service:"
	@curl -s -o /dev/null -w "Status: %{http_code}" http://localhost:3000 || echo "❌ UI not available"
	@echo ""
	@echo ""
	@echo "Docker Services:"
	@docker compose ps

# Generate test dataset
dataset:
	@echo "Generating test dataset..."
	mkdir -p ./test-data
	python3 tools/gen_dataset.py \
		--output-dir ./test-data \
		--xml-count 50 \
		--json-count 50 \
		--include-schema
	@echo "Test dataset generated in ./test-data/"

# Run benchmarks
benchmark: dataset
	@echo "Running benchmarks..."
	./scripts/bench_run.sh

# Run tests
test:
	@echo "Running tests..."
	# Add test commands here when tests are implemented
	@echo "Tests not yet implemented"

# Clean up everything
clean:
	@echo "Cleaning up..."
	docker compose down -v
	docker system prune -f
	@echo "Cleanup completed!"

# Reset all data (destructive)
reset:
	@echo "⚠️  This will delete ALL data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	curl -X POST http://localhost:8000/api/admin/reset \
		-H "Authorization: Bearer devtoken" \
		-H "Content-Type: application/json" \
		-d '{"minio":true,"redis":true,"neo4j":true,"schema":true,"dry_run":true}'
	@echo ""
	@read -p "Proceed with reset? (y/N): " confirm && [ "$$confirm" = "y" ]
	@echo "Performing reset..."
	# Reset command would go here - requires confirm token from dry run

# Development shortcuts
dev-api:
	docker compose logs -f api

dev-ui:
	docker compose logs -f ui

dev-ingestor:
	docker compose logs -f ingestor

# Quick restart of specific services
restart-api:
	docker compose restart api

restart-ui:
	docker compose restart ui

restart-ingestor:
	docker compose restart ingestor