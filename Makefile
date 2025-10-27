.PHONY: help infra-up infra-down infra-logs dev-up dev-down prod-up logs clean-all

# Default shell for cross-platform compatibility (requires Git Bash on Windows)
SHELL := /bin/bash

# Detect current branch
BRANCH := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

# Create a safe project name slug (replace special chars with hyphens)
PROJECT_SLUG := $(shell echo "$(BRANCH)" | sed 's/[^a-zA-Z0-9]/-/g' | sed 's/--*/-/g' | tr '[:upper:]' '[:lower:]')

# Calculate port offset based on branch name (0-9)
# Special case: main always gets offset 0 for default ports
# Uses cksum for cross-platform compatibility
PORT_OFFSET := $(shell \
	if [ "$(BRANCH)" = "main" ]; then \
		echo 0; \
	else \
		echo "$(BRANCH)" | cksum | awk '{print $$1 % 10}'; \
	fi)

# Calculate actual ports
API_PORT := $(shell echo $$((8000 + $(PORT_OFFSET))))
UI_PORT := $(shell echo $$((3000 + $(PORT_OFFSET))))

# Compose project name for container isolation
export COMPOSE_PROJECT_NAME := niem-$(PROJECT_SLUG)
export API_PORT
export UI_PORT

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# ============================================================================
# HELP
# ============================================================================

help: ## Show this help message
	@echo "Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Current configuration:"
	@echo "  Branch:       $(BRANCH)"
	@echo "  Project:      $(COMPOSE_PROJECT_NAME)"
	@echo "  API Port:     $(API_PORT)"
	@echo "  UI Port:      $(UI_PORT)"

# ============================================================================
# INFRASTRUCTURE COMMANDS
# ============================================================================

infra-up: ## Start shared infrastructure (neo4j + minio)
	@echo "$(GREEN)Starting shared infrastructure...$(NC)"
	@docker network inspect niem-infra >/dev/null 2>&1 || docker network create niem-infra
	@docker compose --profile infra up -d
	@echo "$(GREEN)Infrastructure started:$(NC)"
	@echo "  Neo4j Browser:  http://localhost:7474"
	@echo "  Minio Console:  http://localhost:9002"

infra-down: ## Stop shared infrastructure
	@echo "$(YELLOW)Stopping shared infrastructure...$(NC)"
	@docker compose --profile infra down
	@echo "$(GREEN)Infrastructure stopped$(NC)"

infra-logs: ## View infrastructure logs
	@docker compose --profile infra logs -f

# ============================================================================
# DEVELOPMENT MODE
# ============================================================================

dev-up: ensure-infra ## Start application in development mode (hot reload)
	@echo "$(GREEN)Starting development environment...$(NC)"
	@echo "  Project:    $(COMPOSE_PROJECT_NAME)"
	@echo "  API Port:   $(API_PORT)"
	@echo "  UI Port:    $(UI_PORT)"
	@docker compose --profile dev up -d --build
	@echo "$(GREEN)Development environment started:$(NC)"
	@echo "  API:  http://localhost:$(API_PORT)"
	@echo "  UI:   http://localhost:$(UI_PORT)"

dev-down: ## Stop development environment
	@echo "$(YELLOW)Stopping development environment ($(COMPOSE_PROJECT_NAME))...$(NC)"
	@docker compose --profile dev down
	@echo "$(GREEN)Development environment stopped$(NC)"

# ============================================================================
# PRODUCTION MODE
# ============================================================================

prod-up: ensure-infra ## Start application in production mode
	@echo "$(GREEN)Starting production environment...$(NC)"
	@echo "  Project:    $(COMPOSE_PROJECT_NAME)"
	@echo "  API Port:   $(API_PORT)"
	@echo "  UI Port:    $(UI_PORT)"
	@docker compose --profile prod up -d --build
	@echo "$(GREEN)Production environment started:$(NC)"
	@echo "  API:  http://localhost:$(API_PORT)"
	@echo "  UI:   http://localhost:$(UI_PORT)"

# ============================================================================
# LOGS
# ============================================================================

logs: ## View application logs (use: make logs | grep ERROR)
	@docker compose logs -f

# ============================================================================
# CLEANUP
# ============================================================================

clean-all: ## Stop everything (all worktrees + infrastructure)
	@echo "$(YELLOW)Stopping all services and infrastructure...$(NC)"
	@docker compose --profile dev down 2>/dev/null || true
	@docker compose --profile prod down 2>/dev/null || true
	@docker compose --profile infra down 2>/dev/null || true
	@echo "$(GREEN)All services stopped$(NC)"

# ============================================================================
# INTERNAL HELPERS
# ============================================================================

.ensure-infra:
	@if ! docker network inspect niem-infra >/dev/null 2>&1; then \
		echo "$(YELLOW)Infrastructure not running. Starting it now...$(NC)"; \
		$(MAKE) infra-up; \
		echo "$(GREEN)Waiting for infrastructure to be healthy...$(NC)"; \
		sleep 5; \
	fi

ensure-infra: .ensure-infra ## Ensure infrastructure is running (internal)
