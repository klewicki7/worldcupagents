.PHONY: dev db-up db-down migrate seed test lint fmt

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down

migrate: db-up
	cd backend && uv run alembic upgrade head

seed: migrate
	uv --project backend run python -m scripts.load_fixture --all

dev: db-up
	@echo "Starting backend on :8000 and frontend on :3000"
	@(cd backend && uv run uvicorn app.main:app --reload --port 8000 &) ; \
	 (cd worldcupagents-fe && pnpm dev)

test: seed
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run mypy app

fmt:
	cd backend && uv run ruff format .
