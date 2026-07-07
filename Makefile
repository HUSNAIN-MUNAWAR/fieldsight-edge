.PHONY: api web test lint seed migrate edge-demo
api:
	cd apps/api && uvicorn app.main:app --reload --port 8000
web:
	cd apps/web && npm run dev
seed:
	cd apps/api && PYTHONPATH=. python scripts/seed_demo.py
migrate:
	cd apps/api && PYTHONPATH=. alembic upgrade head
test:
	cd apps/api && PYTHONPATH=. pytest -q
lint:
	cd apps/api && ruff check app tests
edge-demo:
	cd apps/edge-agent && python agent.py run-demo-mission --device edge-03
