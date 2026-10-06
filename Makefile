.PHONY: test lint typecheck wp-up wp-down

test:
	PYTHONPATH=src pytest tests/

lint:
	ruff check .

typecheck:
	mypy src tests --exclude '\.venv' --follow-imports=skip

wp-up:
	docker compose up -d

wp-down:
	docker compose down
