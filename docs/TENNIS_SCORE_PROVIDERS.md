# Tennis Score Providers

The bookie tennis module uses pluggable score providers to fetch live match state.
All providers implement the `TennisScoreProvider` interface for seamless swapping.

## Available Providers

### MockProvider (Default)

**Status:** Production-ready for testing and demos

- Three hard-coded matches that advance realistically
- No network calls, no dependencies, no external data
- Perfect for unit tests, local development, demos
- Score advances by one point each poll for realistic streaming simulation

Use when:
- Testing the pairing / recording / bundling pipeline
- Developing locally without internet dependency
- Running CI/CD tests (MockProvider is isolated and deterministic)

```bash
python -m src.sports.tennis.cli list-live --provider mock
python -m src.sports.tennis.cli pair-markets --provider mock --mock-markets
```

### EspnProvider

**Status:** Research / beta — ESPN API is undocumented and can change without notice

Fetches tennis match data from ESPN's public web API endpoints.

**Capabilities:**
- Fetches tournament and match data from ESPN's `/atp/events` and `/wta/events` endpoints
- Parses match scores from full-match string format (e.g., "6-2 7-6(7-5) 3-2")
- Infers tour (ATP/WTA), surface (hard/clay/grass) from tournament name
- Handles both old and new ESPN API response formats (athlete.displayName and direct displayName)
- Tolerates missing fields (returns safe defaults: scores=0, player="Unknown")
- Caches data for 5 seconds to avoid hammering ESPN
- Retry logic with exponential backoff (max 2 retries)
- Handles network failures gracefully (returns empty list, not exceptions)

**Limitations:**
- ESPN API is **undocumented** and can change or break without notice
- Returns tournament matches (some in-progress, some scheduled), not strictly "live" matches
- Player names may differ from Kalshi market names (requires fuzzy matching)
- Full-match score strings require parsing (point-level data unavailable)
- Server identity rarely provided (defaulted to UNKNOWN)
- Surface/tour inferred from tournament name rather than explicit metadata

**Usage:**
```bash
# List live matches from ESPN
python -m src.sports.tennis.cli list-live --provider espn

# Pair ESPN matches to Kalshi markets
python -m src.sports.tennis.cli pair-markets --provider espn --mock-markets

# Record a paired match (ESPN state + Kalshi market)
python -m src.sports.tennis.cli record-paired \
    --provider espn \
    --match-id {espn_match_id} \
    --ticker {kalshi_ticker} \
    --seconds 300
```

**Why ESPN might break:**
- ESPN's API paths or response schema could change
- ESPN could add authentication or rate limiting
- The undocumented endpoints could be deprecated

**Reliability for production:** ❌ NOT RECOMMENDED
- Use EspnProvider for research, prototyping, demos only
- Do not depend on EspnProvider for production trading systems
- Have a fallback plan (MockProvider, manual market pairing)

## Error Handling

Both providers follow the same error contract:

| Method | Behavior |
|--------|----------|
| `list_live_matches()` | Returns empty `[]` on network error (never raises) |
| `get_match_state()` | Raises `KeyError` if match not found; re-raises network errors after retries |
| `stream_match_states()` | Yields silently until 5 consecutive failures; then stops |

This design prevents transient network hiccups from crashing the pipeline while still
surfacing persistent failures.

## Adding a New Provider

Inherit from `TennisScoreProvider` and implement three methods:

```python
from src.sports.tennis.provider_base import TennisScoreProvider, TennisMatchInfo
from src.sports.tennis.state import TennisState

class SportradarProvider(TennisScoreProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key
    
    def list_live_matches(self) -> List[TennisMatchInfo]:
        """Fetch live matches. Return [] on error."""
        ...
    
    def get_match_state(self, match_id: str) -> TennisState:
        """Get current state for one match. Raise KeyError if not found."""
        ...
    
    def stream_match_states(
        self, match_id: str, poll_interval: float = 5.0
    ) -> Iterator[TennisState]:
        """Yield successive snapshots. Caller breaks out of loop."""
        ...
```

Wire it into the CLI:

```python
# In src/sports/tennis/cli.py _make_provider()
if provider_name == "sportradar":
    from src.sports.tennis.sportradar_provider import SportradarProvider
    return SportradarProvider(api_key=os.environ["SPORTRADAR_API_KEY"])
```

Add a test file mocking HTTP responses:

```python
# tests/test_tennis_sportradar_provider.py
from unittest.mock import patch

@patch("src.sports.tennis.sportradar_provider.requests.get")
def test_list_live_matches(mock_get):
    mock_get.return_value.json.return_value = {...}
    provider = SportradarProvider(api_key="test")
    matches = provider.list_live_matches()
    assert len(matches) > 0
```

## Switching Providers in Code

```python
from src.sports.tennis.mock_provider import MockProvider
from src.sports.tennis.espn_provider import EspnProvider
from src.sports.tennis.live_feed import TennisLiveFeed

# Use mock (default, no network)
feed = TennisLiveFeed(MockProvider())

# Use ESPN (research only)
feed = TennisLiveFeed(EspnProvider(timeout=10.0))

# Use custom provider
feed = TennisLiveFeed(YourCustomProvider())

for state, ts in feed.stream("MATCH-123"):
    print(f"{state.player_a} vs {state.player_b}: {state.sets_a}-{state.sets_b}")
```

## Testing and Mocking

All tests should mock HTTP responses, never make real network calls:

```python
from unittest.mock import patch, MagicMock

@patch("src.sports.tennis.espn_provider.urlopen")
def test_espn_provider(mock_urlopen):
    mock_response = MagicMock()
    mock_response.__enter__.return_value.read.return_value = json.dumps({
        "events": [...]
    }).encode("utf-8")
    mock_urlopen.return_value = mock_response
    
    provider = EspnProvider()
    matches = provider.list_live_matches()
    assert len(matches) > 0
```

## Recommendations

| Use case | Provider | Rationale |
|----------|----------|-----------|
| Unit tests | MockProvider | Deterministic, no network, fast |
| Local development | MockProvider | Quick iteration, no internet required |
| CI/CD pipelines | MockProvider | Isolated, reproducible, no flakiness |
| Research / prototyping | EspnProvider or custom | Real-world data, but accept brittleness |
| Production trading | Custom provider | Requires reliability SLA, authentication, monitoring |

**Golden rule:** If your trading system depends on a score provider, it must be
monitored, tested, and replaceable. Undocumented APIs fail. Have a fallback.
