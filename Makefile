# =============================================================================
# AI-Native App Architecture - Makefile
# =============================================================================
# This Makefile provides a simple interface to manage the development stack.
# Commands are designed to be intuitive and composable.
#
# Philosophy:
#   - `make dev` should get you running in one command
#   - `make clean` should reset everything safely
#   - State lives in Docker volumes, secrets live in secrets/
#   - Configuration is generated, never hand-edited

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY := help setup config ollama-setup dev down restart clean destroy rebuild logs shell-db

help: ## Show available commands
	@awk 'BEGIN {FS=":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  %-15s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# =============================================================================
# Setup Commands - Run Once
# =============================================================================

setup: ## Install uv and dependencies (local Python dev environment)
	@# uv is Astral's ultra-fast Python package manager
	@# Only installs if not already present
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@# uv sync reads pyproject.toml and uv.lock to install exact versions
	uv sync

config: ## Generate .env from template (creates/updates secrets)
	@# Runs infra/generate-config.sh which:
	@#   1. Loads API keys from secrets/api/* (e.g., secrets/api/anthropic)
	@#   2. Generates random passwords for databases (cached in secrets/infra/)
	@#   3. Builds connection strings from secrets
	@# Result: .env file ready for docker compose
	infra/generate-config.sh

ollama-setup: ## Pull Ollama models into running container
	@# Only needed if you want local LLM inference (optional)
	@# Reads OLLAMA_PULL_MODELS from .env and pulls each model
	@# Example: make ollama-setup (after stack is running)
	@if docker compose ps ollama >/dev/null 2>&1; then \
		docker compose exec -T ollama /bin/bash -s < infra/setup-ollama.sh; \
	else \
		echo "Ollama container not running - start stack first: make dev"; exit 1; \
	fi

# =============================================================================
# Stack Management - Daily Use
# =============================================================================

dev: config ## Start all services (generates config if needed)
	@# Primary command: starts the entire stack
	@# Runs `config` first to ensure .env is current
	@# Uses docker compose (not docker-compose) - modern CLI
	docker compose up -d
	@echo "✅ Services ready at http://localhost:8000"
	@echo "   API docs: http://localhost:8000/docs"

down: ## Stop all services (preserves volumes and data)
	@# Graceful shutdown - volumes remain, data persists
	@# Use this between sessions, not `clean`
	docker compose down

restart: ## Restart services without wiping state
	@# Quick restart - useful after code changes that need container reload
	@# Note: With hot reload, you rarely need this
	docker compose down
	docker compose up -d
	@echo "♻️ Stack restarted (data preserved)"

# =============================================================================
# Maintenance Commands - Use With Caution
# =============================================================================

clean: ## Remove generated files and volumes (DESTRUCTIVE)
	@# WARNING: Deletes all data (PostgreSQL, Redis, Neo4j, MinIO, Qdrant)
	@# Use when you want a truly fresh start
	@# Removes: Docker volumes, .env file, cached secrets
	docker compose down -v --remove-orphans
	rm -f .env
	rm -f secrets/infra/*
	@echo "🧹 Cleaned: volumes, .env, cached infra secrets"

destroy: clean ## Destroy stack (alias for clean)

rebuild: clean dev ## Full rebuild from scratch
	@# Nuclear option: wipes everything and rebuilds
	@# Use when: Docker state is corrupted, or major infra changes
	@# Equivalent to: make clean && make dev

# =============================================================================
# Debugging & Inspection
# =============================================================================

logs: ## Tail all service logs (Ctrl+C to exit)
	@# Shows logs from all containers in real-time
	@# Useful for debugging startup issues or runtime errors
	docker compose logs -f

shell-db: ## PostgreSQL shell (interactive psql session)
	@# Drops you into psql connected to the appdb database
	@# Useful for inspecting schema, running queries, debugging
	docker compose exec postgres psql -U appuser -d appdb