SHELL := /bin/bash

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: install backend frontend dev

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --port $${BACKEND_PORT:-$(BACKEND_PORT)}

frontend:
	cd frontend && npm run dev -- --port $${FRONTEND_PORT:-$(FRONTEND_PORT)}

dev:
	@set -euo pipefail; \
	( cd backend && uvicorn app.main:app --reload --port $${BACKEND_PORT:-$(BACKEND_PORT)} ) & \
	BACK_PID=$$!; \
	( cd frontend && npm run dev -- --port $${FRONTEND_PORT:-$(FRONTEND_PORT)} ) & \
	FRONT_PID=$$!; \
	trap 'kill $$BACK_PID $$FRONT_PID 2>/dev/null || true' INT TERM EXIT; \
	wait
