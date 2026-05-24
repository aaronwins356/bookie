.PHONY: install test replay replay-blowout lint clean \
	sim-calm sim-panic sim-liquidity sim-endgame sim-all \
	data-validate data-bundle data-inspect replay-bundle

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

# Phase 3 data pipeline
GAME ?= data/examples/raw_game_sample.csv
MARKET ?= data/examples/raw_market_sample.csv
BUNDLE ?= data/examples/replay_bundle.json

data-validate:
	python -m src.data.cli validate --game $(GAME) --market $(MARKET)

data-bundle:
	python -m src.data.cli build-bundle --game $(GAME) --market $(MARKET) --out $(BUNDLE)

data-inspect:
	python -m src.data.cli inspect-bundle --bundle $(BUNDLE)

replay-bundle:
	python -m src.replay.simulator --bundle $(BUNDLE)

lint:
	python -m pyright src tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
