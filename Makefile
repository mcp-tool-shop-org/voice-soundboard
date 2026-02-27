.PHONY: verify test lint build

verify: lint test
	@echo "All checks passed"

test:
	pytest tests/ --ignore=tests/v29_soak/ --ignore=tests/v31_hardening/ -v --cov=voice_soundboard --cov-report=term-missing

lint:
	ruff check voice_soundboard tests

build:
	python -m build --sdist --wheel
