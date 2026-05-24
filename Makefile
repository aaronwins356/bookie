.PHONY: install test replay replay-blowout lint clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

replay:
	python -m src.replay.simulator --scenario comeback

replay-blowout:
	python -m src.replay.simulator --scenario blowout

lint:
	python -m pyright src tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
