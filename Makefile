.PHONY: install test replay replay-blowout lint clean \
	sim-calm sim-panic sim-liquidity sim-endgame sim-all

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

# Scripted (hand-authored) scenarios
replay:
	python -m src.replay.simulator --scenario comeback

replay-blowout:
	python -m src.replay.simulator --scenario blowout

# Simulated microstructure scenarios
sim-calm:
	python -m src.replay.simulator --scenario calm

sim-panic:
	python -m src.replay.simulator --scenario panic

sim-liquidity:
	python -m src.replay.simulator --scenario liquidity_crisis

sim-endgame:
	python -m src.replay.simulator --scenario endgame_chaos

sim-all: sim-calm sim-panic sim-liquidity sim-endgame

lint:
	python -m pyright src tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
