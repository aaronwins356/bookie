# Secrets Management

## Current state

No secrets are required. The engine runs entirely on mock data.

## Future secrets (when going live)

All secrets are loaded from environment variables. Never hardcode them.

| Variable           | Purpose                          |
|--------------------|----------------------------------|
| `KALSHI_API_KEY`   | Kalshi REST API key              |
| `KALSHI_API_SECRET`| Kalshi API secret                |

## How to configure

1. Copy `.env.example` to `.env`
2. Fill in values
3. `.env` is in `.gitignore` — never commit it

## Loading in code

```python
import os
api_key = os.environ["KALSHI_API_KEY"]
```

Or use `python-dotenv` (add to dependencies when needed):

```python
from dotenv import load_dotenv
load_dotenv()
```

## Secret scanning

Before any commit that could touch adapter code, verify:

```bash
git diff HEAD | grep -i "key\|secret\|password\|token"
```

Never commit real credentials. Use the stub adapter for all development.
