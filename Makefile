SHELL      := /bin/sh
COMPOSE    ?= docker compose
PYTHON     ?= python3
MCP_URL    ?= http://localhost:8000/mcp
HEALTH_URL ?= http://localhost:8000/health

.DEFAULT_GOAL := help

.PHONY: help init build up start down stop restart logs ps config check \
        test test-e2e test-e2e-direct test-e2e-mcp test-e2e-mutation-smoke clean

help: ## Show available targets.
	@awk 'BEGIN {FS = ":.*##"; printf "SkyQ MCP targets:\n\n"} \
	      /^[a-zA-Z0-9_-]+:.*##/ {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

init: ## Create .env from .env.example if it does not exist yet.
	@if [ -f .env ]; then \
	  echo ".env already exists"; \
	else \
	  cp .env.example .env; \
	  echo "Created .env — set SKYQ_HOST to your Sky Q box IP before starting."; \
	fi

# ---------------------------------------------------------------------------
# Docker lifecycle
# ---------------------------------------------------------------------------

build: ## Build the Docker image.
	$(COMPOSE) build

up: ## Start the MCP server in the foreground.
	$(COMPOSE) up --build

start: ## Start the MCP server in the background.
	$(COMPOSE) up --build -d
	@echo "MCP endpoint : $(MCP_URL)"
	@echo "Health check : $(HEALTH_URL)"

down: ## Stop and remove the Compose containers.
	$(COMPOSE) down

stop: down ## Alias for down.

restart: down start ## Restart the MCP server in the background.

logs: ## Follow service logs.
	$(COMPOSE) logs -f skyq-mcp

ps: ## Show Compose service status.
	$(COMPOSE) ps

config: ## Render and validate the Compose configuration.
	$(COMPOSE) config

# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

check: ## Run local syntax and Compose configuration checks.
	$(PYTHON) -m compileall src tests
	$(COMPOSE) config >/dev/null
	@echo "All checks passed."

lint: ## Run ruff linter.
	$(PYTHON) -m ruff check src tests

fmt: ## Auto-format with ruff.
	$(PYTHON) -m ruff format src tests

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

test: ## Run unit tests (no Sky Q box required).
	$(PYTHON) -m pytest tests/ -v

test-e2e: build ## Run full end-to-end tests inside Docker (requires .env with real SKYQ_HOST).
	$(COMPOSE) run --rm skyq-mcp python -m tests.e2e

test-e2e-direct: build ## Test the Sky Q box directly (no MCP layer).
	$(COMPOSE) run --rm skyq-mcp python -m tests.e2e --skip-mcp

test-e2e-mcp: build ## Test only the MCP HTTP layer.
	$(COMPOSE) run --rm skyq-mcp python -m tests.e2e --skip-direct

test-e2e-mutation-smoke: build ## Test mutation tools (sends key press to receiver).
	$(COMPOSE) run --rm \
	  -e SKYQ_ALLOW_MUTATIONS=true \
	  -e E2E_MUTATION_SMOKE=true \
	  skyq-mcp python -m tests.e2e --skip-direct

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean: ## Remove local Python cache artefacts.
	find src tests -type d -name __pycache__ -prune -exec rm -rf {} +
