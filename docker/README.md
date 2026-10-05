# RedTraces AI local Docker setup

From the repository root, with Docker Desktop running Linux containers:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 100
```

The root `.env` holds generated database passwords and `UNIFIED_CTI_API_KEY`.
Do not commit it. All published ports bind only to this computer.

| Service | Address |
| --- | --- |
| Dashboard | http://localhost:3500 |
| Forum API docs | http://localhost:5000/docs |
| Unified API docs | http://localhost:8100/docs |
| Telegram API docs | http://localhost:8101/docs |
| Advanced Telegram / RedTraces API docs | http://localhost:8200/docs |
| X API docs | http://localhost:8102/docs |
| Facebook API docs | http://localhost:8103/docs |
| Instagram API docs | http://localhost:8104/docs |

The dashboard Connections page defaults to these ports. If an old browser
configuration is saved, reset its addresses there and save.

## What this project does

RedTraces AI is a cyber threat intelligence (CTI) analyst dashboard. It brings
forum and social-media findings together, with a particular focus on threats
to Pakistani organizations, government domains, and personal data. Collector
rules match entity/domain indicators alongside threat terms and assign severity.
These are rule-based signals for analyst review, not proof of a breach.

The browser calls five Python APIs. X, Facebook, Instagram and Telegram store findings and
monitored targets in separate MySQL databases. The forum API stores ingested
alerts in SQLite and supports keyword, date, period and score filters.
The UI periodically refreshes module results and provides keyword searches.

A separate unified FastAPI service accepts normalized web, Telegram, X, forum
and manual findings. It validates input and deduplicates it using a SHA-256
fingerprint. This store is independent of the source databases: automatic
forwarding from collectors to the unified store is not implemented.

## Local API mode

`ENABLE_LIVE_COLLECTION=false` is the default. All API services and database
operations work without social credentials, while background polling stays off.
Empty databases mean no findings, not failed services. Source API availability
does not mean an authenticated crawler is running.

The Docker collector sources in `docker/collectors` are isolated adaptations
of the supplied scripts. They use environment settings instead of embedded
credentials, have dedicated social databases, and persist X account state in
a volume. The forum service implements the dashboard contract and authenticated
manual ingestion; it does not start the interactive browser crawler.
Existing host databases, cookies, browser profiles and sessions are not imported.
The older source folders contain embedded credentials; rotate those before
using them for live collection. They are excluded from Docker build contexts.

Telegram is integrated into the dashboard at port 8101. ShadowWatch remains a separate legacy component.

## APIs

* Social APIs: `GET /leaks`, `GET /channels`, `GET /accounts`, and
  `GET /search-leaks?keyword=...`. X, Facebook and Instagram use
  `POST /add-channel` with `{"username":"your-target"}`; Telegram uses
  `{"link":"@channel-or-t.me-link"}`. Use `/docs` for each full API.
* Forums: `GET /api/health`, `GET /api/data?period=7d&search=...`,
  and authenticated `POST /api/alerts`.
* Unified: `GET /api/v1/health`, `GET /api/v1/findings`, and
  authenticated `POST /api/v1/findings`.

For forum and unified writes, supply `X-API-Key` with the value from `.env`.
Example unified request body:

```json
{
  "source_type": "manual",
  "source_name": "Analyst review",
  "external_id": "example-001",
  "title": "Example finding",
  "content": "An analyst-provided observation, not collected live data.",
  "severity": "low",
  "confidence": 50
}
```

## Where to add API credentials

Copy [`.env.example`](../.env.example) to the root `.env` only if you are
starting from a new installation. This computer already has `.env`; add values
there and restart the affected service with `docker compose up -d --force-recreate <service>`.

| Source | Add to `.env` | Restart | Notes |
| --- | --- | --- | --- |
| Unified findings API | `UNIFIED_CTI_API_KEY` | `unified-api` | Required for `POST /api/v1/findings` and forum alert ingestion. |
| X | `X_USERNAME`, `X_AUTH_TOKEN`, `X_CT0`; set `ENABLE_LIVE_COLLECTION=true` | `twitter` | All three session values are required. |
| Telegram | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`; set `TELEGRAM_ENABLED=true` after completing session login | `telegram` | Add only channels you are authorized to monitor. |
| Facebook | `PKCERT_FB_COOKIES`; set `ENABLE_LIVE_COLLECTION=true` | `facebook` | The crawler package and a valid authorized cookie file are also required. |
| Instagram | `PKCERT_IG_USER` plus `PKCERT_IG_SESSIONFILE` or `PKCERT_IG_PASS`; set `ENABLE_LIVE_COLLECTION=true` | `instagram` | The crawler package and an authorized account are also required. |

Keep `.env` private. Never add credentials to dashboard fields, source files, Git, or this guide.

Social management endpoints retain the original local-only access model and
have no authentication. Do not expose this development stack publicly.

## Live collection later

First configure the chosen accounts and targets. X uses `X_USERNAME`,
`X_AUTH_TOKEN`, and `X_CT0` or a configured twscrape account pool. Facebook and
Instagram require their optional crawler packages and valid sessions/cookies;
those crawler packages are deliberately not installed in this API-only image.
Do not enable polling until those dependencies and sessions have been configured.
Interactive forum browsing needs separate browser setup and operator login.

## Persistence and operations

Named Docker volumes retain MySQL, forum, unified, X account and Telegram session data.
`docker compose stop` stops services; `docker compose up -d` restarts them.
`docker compose down` removes containers but retains volumes. Adding `-v`
deletes stored data, so do not use it unless a reset is intended.

The original `npm test` suite still targets the removed starter skeleton;
it is not a valid acceptance test for the current dashboard. Use the Docker
build, health checks and `docker compose exec unified-api python /app/smoke_test.py`
for this local deployment. The smoke test uses a temporary database and does
not leave fake findings in the live store.

## This device

Docker data is stored at D:\DockerDesktopData\disk. A directory junction preserves the original Docker path on C:. Keep D: available whenever Docker is running. The disk copy was SHA-256 verified before the original disk file was removed.

For a fresh checkout, run docker/setup.ps1 to generate local credentials and start the stack.



## Verified deployment (2026-09-23)

All eight services, including Telegram, are healthy. Dashboard and all source API read endpoints returned HTTP 200. The isolated smoke test passed authentication, ingestion, timestamps, deduplication, validation and forum filters. Live polling remains disabled; no synthetic test findings were added to production databases.

The original disk-full incident damaged cached base layers. This device uses the hexsentry-builder Docker Buildx builder, Node 22 Alpine, and MySQL 8.4.6 to avoid those layers. For a rebuild on this device:

    docker compose build --builder hexsentry-builder
    docker compose up -d --no-build

For normal restarts, use docker compose up -d. To stop the project, use docker compose stop.



## Telegram integration

The dashboard now includes Telegram navigation, source counts, connection tests,
channel targets and keyword results. Its API is at http://localhost:8101/docs.
The service adapts `private_collectors_updated/telegram_collector.py`, uses its
classification rules and MySQL schema, and stores session state in the
`telegram-data` Docker volume. Existing host sessions are not imported.

Local-only mode is the default: the API runs without Telegram credentials.
Public handles added through the dashboard are saved as configured targets;
private invitations require an authenticated session. Adding a target while
online can join that channel using the configured Telegram account. Incoming
messages are processed only from configured channels. Historical rows without
severity are displayed as unknown, rather than assigned a fabricated risk score.

To enable collection later, add your own `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`
to the root `.env`, then perform the interactive login yourself:

```powershell
docker compose stop telegram
docker compose run --rm telegram python -c "import os; from telethon.sync import TelegramClient; c=TelegramClient('/data/monitor_session', int(os.environ['TELEGRAM_API_ID']), os.environ['TELEGRAM_API_HASH']); c.start(); c.disconnect()"
```

Set `TELEGRAM_ENABLED=true` in `.env` and run `docker compose up -d telegram`.
Re-add configured channels after login to resolve and join them. To turn off
collection, set `TELEGRAM_ENABLED=false` and recreate the Telegram service.
The switch is independent from the other collectors' `ENABLE_LIVE_COLLECTION`.

For an existing MySQL volume, apply the additive schema grants once after updating:

```powershell
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root < /docker-entrypoint-initdb.d/init.sql'
```

Telegram smoke test (requires collection disabled; removes its temporary records):

```powershell
Get-Content tests/telegram-api-smoke.py -Raw | docker compose exec -T telegram python -
```


Telegram integration smoke tests passed; all temporary test records were removed.

## Combined RedTraces Telegram pipeline

The supplied `redtracesai` project is included under
[`redtraces-core`](../redtraces-core). Its source is kept separate from the
existing MySQL Telegram monitor so neither data store, channel registry, or API
is replaced. Docker adds three services:

| Service | Purpose | Address |
| --- | --- | --- |
| `redtraces-postgres` | Advanced Telegram message and metadata store | Internal only |
| `redtraces-redis` | Noise-filter cache and metrics | Internal only |
| `redtraces-api` | Message history, live stream, IOC and artifact APIs | http://localhost:8200/docs |
| `redtraces-telegram` | Telethon discovery, backfill and live listener | Internal only |

The dashboard’s Telegram page combines rows from port 8101 and port 8200. The
Connections page tests and saves both addresses. The advanced listener starts
in a healthy standby state until its Telegram credentials and at least one
explicitly authorized public channel are configured.

To enable that listener, add the following to the root `.env`, then recreate
only the advanced collector:

```dotenv
REDTRACES_DB_PASSWORD=use-a-local-secret-instead-of-the-default
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
REDTRACES_TELEGRAM_CHANNELS=first_public_channel,second_public_channel
REDTRACES_TELEGRAM_DISCOVERY_ENABLED=false
REDTRACES_TELEGRAM_AUTO_JOIN=false
```

Complete its Telethon login interactively, which persists only in the
`redtraces-telegram-session` Docker volume:

```powershell
docker compose run --rm redtraces-telegram python -c "from telethon.sync import TelegramClient; import os; c=TelegramClient('/sessions/redtracesai', int(os.environ['TELEGRAM_API_ID']), os.environ['TELEGRAM_API_HASH']); c.start(); c.disconnect()"
docker compose up -d --force-recreate redtraces-telegram
```

The advanced collector defaults to no discovery and no automatic joins. Enable
those two settings only for channels that the configured account is authorized
to monitor. Its original Discord, Reddit, dark-web, auto-discovery, STIX,
Sigma, YARA, and SIEM source modules are retained in `redtraces-core`; this
combined stack starts only its Telegram services.

## Read-only public API gateway

Port 8200 is the primary Telegram API used by the dashboard. It combines the
RedTraces PostgreSQL pipeline with the retained local Telegram monitor at
port 8101, so existing managed channels and collected rows remain visible.
It also provides unauthenticated, read-only local gateway endpoints for the
other running collectors:

```text
GET http://localhost:8200/api/public/health
GET http://localhost:8200/api/public/messages?platform=telegram
GET http://localhost:8200/api/public/messages?platform=twitter
GET http://localhost:8200/api/public/messages?platform=facebook
GET http://localhost:8200/api/public/messages?platform=instagram
GET http://localhost:8200/api/public/messages?platform=forums
```

These addresses bind to `127.0.0.1`, so they are public to local applications
on this device but are not exposed to the internet. Telegram compatibility
endpoints at port 8200 (`/leaks`, `/channels`, `/accounts`,
`/search-leaks`, and `/add-channel`) keep the dashboard channel controls
working while the RedTraces API becomes the primary endpoint.

