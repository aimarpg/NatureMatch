.PHONY: install dev test test-hw lint run-station run-api stack-up stack-down
install:
	python -m venv .venv && .venv/bin/pip install -e ".[pi]"
dev:
	pip install -e ".[dev]"
test:
	pytest
test-hw:
	pytest -m hardware
lint:
	ruff check . && mypy src
run-station:
	nm-station --config config/station.yaml
run-api:
	nm-api
stack-up:
	docker compose -f deploy/docker/compose.yml up -d
stack-down:
	docker compose -f deploy/docker/compose.yml down
