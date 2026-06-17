# MyLean Law Unofficial API

Unofficial Python integrations for MyLean Law.

## Integrations

- `mylean_law_add_user_to_matter_billing.py` - `add_user_to_matter_billing`.
- `mylean_law_get_calendar_entries.py` - `get_calendar_entries`.
- `mylean_law_create_expense.py` - `create_expense`.
- `mylean_law_list_client_matters.py` - `list_client_matters`.

## Usage

Each file exposes a `run(input, context)` or `run(headers, input)` style entrypoint, matching the source integration runtime.
Authenticated request headers/cookies are expected to be supplied by the caller when required.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Info

This unofficial API is built by [Integuru.ai](https://integuru.ai/).

For custom requests or hosted authentication, contact richard@taiki.online.

See the [complete list of APIs by Integuru](https://github.com/Integuru-AI/APIs-by-Integuru).
