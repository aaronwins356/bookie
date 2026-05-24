import pytest
from src.replay.scenario_engine import ScenarioEngine
from src.replay.simulator import run, _run_simulated
from src.engine.router import PortfolioRouter, PortfolioState
from src.engine.risk import RiskManager, RiskConfig
from src.simulation.market_regime import MarketRegime
from src.strategies import FavoriteGrinder, MomentumStrategy
from src.storage.replay_store import ReplayStore


SCENARIOS = ["calm", "panic", "liquidity_crisis", "endgame_chaos"]


class TestScenarioEngine:
    def test_all_scenarios_generate_ticks(self):
        eng = ScenarioEngine(seed=42)
        for sc in SCENARIOS:
            ticks = eng.generate(sc)
            assert len(ticks) >= 5
            for game, markets, ctx in ticks:
                assert markets[0].spread >= 0
                assert ctx.liquidity.depth > 0
                assert isinstance(ctx.micro_regime, MarketRegime)

    def test_deterministic_with_seed(self):
        a = ScenarioEngine(seed=7).generate("panic")
        b = ScenarioEngine(seed=7).generate("panic")
        assert [t[2].mid for t in a] == [t[2].mid for t in b]

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError):
            ScenarioEngine().generate("does_not_exist")


class TestSimulatedRun:
    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_run_simulated_no_error(self, scenario, capsys):
        _run_simulated(scenario, seed=42)
        out = capsys.readouterr().out
        assert "MICROSTRUCTURE SIMULATOR" in out
        assert "ANALYTICS" in out
        assert "Replay complete" in out

    def test_run_dispatches_scripted(self, capsys):
        run(scenario="comeback")
        assert "GAME STATE" in capsys.readouterr().out


class TestPortfolioRouter:
    def _strats(self):
        return {FavoriteGrinder.NAME: FavoriteGrinder(), MomentumStrategy.NAME: MomentumStrategy()}

    def test_max_concurrent_strategies(self):
        from src.models import Signal, SignalDirection
        router = PortfolioRouter(max_concurrent_strategies=1)
        strats = self._strats()
        sigs = [
            Signal("favorite_grinder", "m", SignalDirection.BUY, 0.9, 70, 55, 15),
            Signal("momentum", "m2", SignalDirection.BUY, 0.8, 65, 55, 10),
        ]
        intents = router.allocate(sigs, strats, MarketRegime.CALM, PortfolioState())
        assert len(intents) == 1   # capped at 1 concurrent strategy

    def test_cooldown_blocks_repeat(self):
        from src.models import Signal, SignalDirection
        router = PortfolioRouter(max_concurrent_strategies=3, cooldown_ticks=2)
        strats = self._strats()
        pf = PortfolioState()
        sig = Signal("favorite_grinder", "m", SignalDirection.BUY, 0.9, 70, 55, 15)
        first = router.allocate([sig], strats, MarketRegime.CALM, pf)
        assert len(first) == 1
        # immediately again → on cooldown
        sig2 = Signal("favorite_grinder", "m", SignalDirection.BUY, 0.9, 70, 55, 15)
        second = router.allocate([sig2], strats, MarketRegime.CALM, pf)
        assert len(second) == 0

    def test_regime_scaling_affects_size(self):
        from src.models import Signal, SignalDirection
        router = PortfolioRouter()
        strats = self._strats()
        sig_fav = Signal("favorite_grinder", "m", SignalDirection.BUY, 0.9, 70, 55, 15)
        favored = router.allocate([sig_fav], strats, MarketRegime.CALM, PortfolioState())
        sig_averse = Signal("favorite_grinder", "m", SignalDirection.BUY, 0.9, 70, 55, 15)
        averse = router.allocate([sig_averse], strats, MarketRegime.ENDGAME_CHAOS, PortfolioState())
        assert favored[0].size >= averse[0].size


class TestRiskRegimeScaling:
    def test_regime_scale_lookup(self):
        rm = RiskManager()
        assert rm.regime_scale(MarketRegime.CALM) >= rm.regime_scale(MarketRegime.LIQUIDITY_COLLAPSE)

    def test_volatility_adjusted_size_shrinks(self):
        rm = RiskManager()
        base = rm.volatility_adjusted_size(100, MarketRegime.CALM, volatility=1.0)
        high_vol = rm.volatility_adjusted_size(100, MarketRegime.CALM, volatility=4.0)
        assert high_vol < base

    def test_thin_liquidity_caps_size(self):
        rm = RiskManager()
        size = rm.volatility_adjusted_size(1000, MarketRegime.CALM, volatility=1.0, liquidity_depth=100)
        assert size <= 10   # 10% of depth


class TestReplayStore:
    def test_round_trip(self, tmp_path):
        eng = ScenarioEngine(seed=1)
        ticks = [(g, m) for g, m, _ in eng.generate("calm")]
        store = ReplayStore(tmp_path / "scenario.json")
        store.save(ticks)
        loaded = store.load()
        assert len(loaded) == len(ticks)
        assert loaded[0][0].game_id == ticks[0][0].game_id
