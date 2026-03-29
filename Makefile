COMPOSE_FILE=infra/docker/docker-compose.local.yml

.PHONY: infra-up infra-down api-dev web-dev

infra-up:
	docker compose -f $(COMPOSE_FILE) up -d

infra-down:
	docker compose -f $(COMPOSE_FILE) down

api-dev:
	cd backend/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web-dev:
	cd frontend/web && npm run dev
