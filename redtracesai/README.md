# RedTraces AI

Shared collection and API foundation for Telegram, Reddit, and dark-web
messages, backed by PostgreSQL.

## Prerequisites

- Python 3.11+
- Docker with Docker Compose

## Setup

```bash
cd redtracesai
python -m venv .venv
# PowerShell:
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d postgres
python -m scripts.init_db
docker compose exec postgres psql -U redtraces -d redtracesai \
  -c "\d collected_messages"
```

On macOS/Linux, activate the environment with `source .venv/bin/activate` and
copy the environment file with `cp .env.example .env`.

Run the API from the project directory:

```bash
uvicorn api.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Make targets

- `make up` starts PostgreSQL.
- `make down` stops the Compose stack.
- `make logs` follows PostgreSQL logs.
- `make psql` opens a PostgreSQL shell.

For now, `init_db()` uses SQLAlchemy's `create_all`. Add Alembic before making
schema changes in deployed environments.

## Reddit collector

Set the Reddit credentials and comma-separated `REDDIT_SUBREDDITS` in `.env`,
then start the database and collector:

```bash
docker compose up -d postgres reddit_collector
docker compose logs -f reddit_collector
```

After it has polled for a few minutes, verify collected rows:

```bash
docker compose exec postgres psql -U redtraces -d redtracesai \
  -c "SELECT count(*) FROM collected_messages WHERE platform = 'reddit';"
```

## Telegram collector

Set `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and one public channel in
`TELEGRAM_CHANNELS` in `.env`. The collector uses an MTProto user session, not
the Bot API. Perform the first login interactively so Telethon can ask for the
phone number, login code, and two-factor password if enabled:

```bash
docker compose up -d postgres
docker compose run --rm telegram_collector
```

The resulting session is retained in the `telegram_session` named volume.
Stop the interactive process after the initial backfill, then start the
long-running service:

```bash
docker compose up -d telegram_collector
docker compose logs -f telegram_collector
```

Manual test: use one real public channel, allow the startup backfill to finish,
then open PostgreSQL:

```bash
make psql
```

At the `psql` prompt:

```sql
SELECT count(*)
FROM collected_messages
WHERE platform = 'telegram';
```

## Dark-web collector

Set comma-separated, explicitly approved onion URLs in `DARKWEB_TARGETS`.
Requests use Tor's remote-DNS SOCKS mode (`socks5h`) and are delayed between
targets. Change `TOR_CONTROL_PASSWORD` from its development default.

```bash
docker compose up -d --build postgres tor darkweb_collector
docker compose logs -f tor darkweb_collector
```

The included `ExampleForumAdapter` documents placeholder HTML selectors.
Register a real domain-specific adapter in `ADAPTERS` before monitoring that
site. Scrapy-Splash is a possible later upgrade for forums that require
JavaScript rendering.

Run the mocked parse-to-insert pipeline test:

```bash
python -m unittest tests.test_darkweb_collector
```

## Dashboard

The dashboard loads paginated Telegram history from FastAPI and layers a live
SSE feed on top. SSE polls PostgreSQL every three seconds for this MVP.

```bash
docker compose up -d --build postgres api frontend
```

Open the dashboard at `http://localhost:5173` and the API documentation at
`http://localhost:8000/docs`.

## CTI discovery

All collectors share the comma-separated `CTI_KEYWORDS` setting:

- Telegram searches for matching public channels, joins at most
  `TELEGRAM_MAX_CHANNELS`, backfills them, and listens for new messages.
- Reddit discovers up to `REDDIT_MAX_SUBREDDITS` matching communities and
  monitors them. Reading public subreddits does not require account
  subscription.
- Dark-web collection starts only from approved `DARKWEB_TARGETS`, then follows
  same-domain links up to `DARKWEB_MAX_DEPTH` and
  `DARKWEB_MAX_PAGES_PER_TARGET`. It does not register forum accounts or bypass
  authentication.
- With `CTI_FILTER_CONTENT=true`, collectors store only content matching at
  least one configured CTI keyword.

Automatic Telegram joining changes the authenticated Telegram account. Keep
the configured channel limit conservative and review collector logs for flood
waits and failed joins.

## IOC extraction

Every collector extracts and normalizes SHA-256, SHA-1, MD5, URLs, IPv4,
IPv6, and domains from collected text, including common defanged forms such as
`hxxps://host[.]example`. Results are stored in each message's `metadata.iocs`
object with an `ioc_count`.

The dashboard labels these indicators as **Fetched IOCs** and includes a
**Fetched IOCs only** filter.

## Dashboard demo mode

To view the dashboard without API credentials, PostgreSQL, or collectors, set:

```dotenv
VITE_DEMO_MODE=true
```

Then start only the frontend:

```bash
docker compose up -d --build frontend
```

Open `http://localhost:5173`. Set `VITE_DEMO_MODE=false` and recreate the
frontend service when the live API is ready.
