.PHONY: up down build test lint k8s-apply clean logs

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

build:
	docker build -t incident-resolution-app:latest .

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/
	mypy src/

# ---------------------------------------------------------------------------
# Kubernetes
# ---------------------------------------------------------------------------

k8s-apply:
	kubectl apply -k k8s/

k8s-delete:
	kubectl delete -k k8s/

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

clean:
	docker-compose down -v --remove-orphans
	docker image rm incident-resolution-app:latest 2>/dev/null || true
