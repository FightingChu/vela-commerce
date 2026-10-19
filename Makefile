.PHONY: install install-dev test lint run migrate revision shell clean

PY ?= python3
PIP ?= pip3

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

test:
	$(PY) -m pytest tests

# 目前没有统一 lint,老代码过不了 ruff,先只查新增目录
lint:
	$(PY) -m compileall -q vela

run:
	$(PY) -m vela.api.app

migrate:
	$(PY) -m alembic upgrade head

revision:
	$(PY) -m alembic revision -m "$(m)"

shell:
	$(PY) -m vela.shell

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
