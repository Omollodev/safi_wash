# Safi Wash -- developer shortcuts.   Run `make help` to see everything.
#
# Uses your existing virtualenv (.venv or venv) or creates .venv for you.

VENV      ?= $(firstword $(wildcard .venv venv) .venv)
PY         = $(VENV)/bin/python
PIP        = $(VENV)/bin/pip
MANAGE     = $(PY) manage.py

# Pinned tool versions (bump deliberately; Dependabot/you review changes)
GITLEAKS_IMAGE = ghcr.io/gitleaks/gitleaks:v8.30.1
TRIVY_IMAGE    = aquasec/trivy:0.76.1
HADOLINT_IMAGE = hadolint/hadolint:v2.15.1

COMPOSE_DEV  = docker compose -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_TEST = docker compose -f docker-compose.test.yml

.DEFAULT_GOAL := help
.PHONY: help venv install env migrate seed superuser run test check \
        security bandit audit gitleaks gitleaks-history \
        docker-build docker-up docker-down docker-logs docker-dev docker-test docker-security \
        docker-lint docker-scan compose-validate clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- local development
$(VENV)/bin/python:
	python3 -m venv $(VENV)

venv: $(VENV)/bin/python ## Create the virtualenv if it does not exist

install: venv ## Install all dependencies (app + security tools)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

env: ## Create .env from .env.example (never overwrites an existing .env)
	@test -f .env && echo ".env already exists - left untouched" || (cp .env.example .env && echo "Created .env - now edit it")

migrate: ## Apply database migrations
	$(MANAGE) migrate

seed: ## Load demo services + one demo user per role (password printed once)
	$(MANAGE) seed_demo

superuser: ## Create an admin account interactively
	$(MANAGE) createsuperuser

run: ## Start the dev server on http://127.0.0.1:8000
	$(MANAGE) runserver

test: ## Run the test suite
	$(MANAGE) test --noinput

check: ## Django system check + migrations up to date
	$(MANAGE) check
	$(MANAGE) makemigrations --check --dry-run

# ---------------------------------------------------------------- DevSecOps: security scans
security: bandit audit gitleaks ## Run every local security scan

bandit: ## Static analysis of our own code (SAST)
	$(VENV)/bin/bandit -q -r apps config -x '*/tests/*,apps/core/testing.py' -ll

audit: ## Check dependencies for known vulnerabilities (SCA)
	$(VENV)/bin/pip-audit -r requirements.txt

gitleaks: ## Scan the working tree for leaked secrets
	@if command -v gitleaks >/dev/null 2>&1; then \
	  gitleaks dir . -c .gitleaks.toml --no-banner; \
	else \
	  docker run --rm -v "$(CURDIR):/repo" $(GITLEAKS_IMAGE) dir /repo -c /repo/.gitleaks.toml --no-banner; \
	fi

gitleaks-history: ## Scan the WHOLE git history for leaked secrets
	@if command -v gitleaks >/dev/null 2>&1; then \
	  gitleaks git . -c .gitleaks.toml --no-banner; \
	else \
	  docker run --rm -v "$(CURDIR):/repo" $(GITLEAKS_IMAGE) git /repo -c /repo/.gitleaks.toml --no-banner; \
	fi

# ---------------------------------------------------------------- Docker
docker-build: ## Build the production image
	docker build --target runtime -t carwash-pro:latest .

docker-up: ## Start the production-style stack (needs .env with real values)
	docker compose up -d --build

docker-down: ## Stop the production-style stack (keeps data volumes)
	docker compose down

docker-logs: ## Follow the web container logs
	docker compose logs -f web

docker-dev: ## Dev stack: live code reload + PostgreSQL
	$(COMPOSE_DEV) up --build

docker-test: ## Run the test suite in containers against a throw-away PostgreSQL
	$(COMPOSE_TEST) run --rm --build tests; status=$$?; $(COMPOSE_TEST) down -v; exit $$status

docker-security: ## Run bandit + pip-audit in containers
	$(COMPOSE_TEST) run --rm --build security; status=$$?; $(COMPOSE_TEST) down -v; exit $$status

docker-lint: ## Lint the Dockerfile with hadolint
	docker run --rm -i $(HADOLINT_IMAGE) < Dockerfile

docker-scan: docker-build ## Scan the built image for HIGH/CRITICAL vulnerabilities (Trivy)
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $(TRIVY_IMAGE) \
	  image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 carwash-pro:latest

compose-validate: ## Check the compose files are valid
	@printf 'DJANGO_SECRET_KEY=x\nPOSTGRES_PASSWORD=x\n' > .env.ci-check
	docker compose --env-file .env.ci-check config -q && echo "prod compose OK"
	docker compose --env-file .env.ci-check -f docker-compose.yml -f docker-compose.dev.yml config -q && echo "dev compose OK"
	$(COMPOSE_TEST) config -q && echo "test compose OK"
	@rm -f .env.ci-check

clean: ## Remove caches and the local SQLite database
	find . -name __pycache__ -not -path "./$(VENV)/*" -prune -exec rm -rf {} +
	rm -f db.sqlite3
