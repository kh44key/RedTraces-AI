# RedTraces AI

Shared collection and API foundation for Telegram, Discord, Reddit, and
dark-web messages, backed by PostgreSQL.

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

## Discord collector

Create a Discord application and bot, enable the **Message Content Intent** in
the Discord developer portal, and invite the bot to each server with View
Channel, Read Message History, and Read Messages permissions. Discord bots
cannot join servers by keyword; server owners must explicitly invite them.

Set `DISCORD_BOT_TOKEN` and the comma-separated numeric
`DISCORD_CHANNEL_IDS` in `.env`, then run:

```bash
docker compose up -d --build postgres discord_collector
docker compose logs -f discord_collector
```

The collector backfills up to `DISCORD_BACKFILL_LIMIT` messages per configured
channel and then listens live. Confirm inserts with:

```sql
SELECT count(*)
FROM collected_messages
WHERE platform = 'discord';
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

`TELEGRAM_CONNECTION_MODE` supports `full`, `abridged`, and `obfuscated`
Telethon transports. The default is `obfuscated`, which can help on networks
that interfere with recognizable MTProto traffic. If the network still closes
the handshake, configure an authorized SOCKS5 proxy, for example
`socks5h://host.docker.internal:1080`, in `TELEGRAM_PROXY_URL`. A proxy running
on the Windows host must use `host.docker.internal` from Docker rather than
`localhost`. Keep proxy credentials only in `.env`.

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

## Auto-discovery collector

Auto-discovery uses a provider interface and the official Google Programmable
Search JSON API for existing customers. It does not scrape Google result pages
and does not fetch, probe, or interact with discovered URLs. It stores only the
public result title, snippet, URL, source domain, search query, rank, Layer 2
metadata, Layer 3 preprocessing, and extracted IOCs.

Set `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ID` in `.env`. Separate custom queries
with `||`; commas remain part of a query:

```dotenv
AUTODISCOVERY_QUERIES="ransomware" "indicators of compromise"||"malware report" "SHA256"
```

Then run:

```bash
docker compose up -d --build postgres autodiscovery_collector
docker compose logs -f autodiscovery_collector
```

Verify:

```sql
SELECT source, url, metadata->>'search_query'
FROM collected_messages
WHERE platform = 'autodiscovery'
ORDER BY collected_at DESC
LIMIT 20;
```

Google currently documents this API as unavailable to new customers and
scheduled for discontinuation on January 1, 2027. The provider boundary is
intentional so a supported search API can replace Google CSE later without
changing the collection or processing pipeline.

Automatic Telegram joining changes the authenticated Telegram account. Keep
the configured channel limit conservative and review collector logs for flood
waits and failed joins.

## Layered workflow status

Layer 1 collection includes Telegram (MTProto), Discord (bot), Reddit, dark
web, and provider-driven auto-discovery. Signal remains outside the current
scope. Every accepted message uses the same PostgreSQL model.

Layer 2 is implemented as the shared `common.noise` pipeline. It removes empty,
low-signal, repetition-spam, unsupported-language, and same-source duplicate
content. It labels EN/RU/ZH/AR/FA/TR content (plus `unknown` for short or
ambiguous messages) and records the decision and normalized SHA-256 under
`metadata.noise`. Short messages containing IOCs and attachment-only messages
are retained. Configure it with the `NOISE_*` environment settings.

Layer 3 is implemented in `common.preprocessing`. It preserves `raw_text` while
performing HTML decoding, Unicode NFKC normalization, invisible/control
character removal, whitespace normalization, and deterministic defanging
reversal for `hxxp(s)`, bracketed/textual dots, bracketed scheme separators,
and the workflow's `meow://` example. The normalized text, transformation
audit, preprocessing version, and SHA-256 are stored under
`metadata.preprocessing`.

Layer 4 regex IOC extraction consumes the Layer 3 normalized text. The next new
layer to build is the NLP extraction stage.

## STIX 2.1 export

`common.ioc_normalizer` flattens the grouped `metadata.iocs` structure into
canonical provenance-aware IOC records. `common.stix_generator` converts each
record into a STIX 2.1 Indicator, creates one source Identity per
platform/source pair, and adds an `indicates` Relationship for provenance. The
Indicator also carries `created_by_ref` and `x_redtraces_*` provenance fields.

Bundles are validated with the `stix2` built-in validator before being written
atomically to `/output/stix_bundles/{timestamp}.json`. The API service maps that
container path to the local `output/` directory.

Generate a bundle from a JSON array of normalized records:

```bash
docker compose run --rm api python -m scripts.generate_stix /app/records.json
```

Each input item has this shape:

```json
{
  "ioc_type": "ipv4",
  "value": "1.2.3.4",
  "platform": "telegram",
  "source": "falconfeedsio",
  "source_url": "https://t.me/falconfeedsio/7",
  "message_id": "7",
  "confidence": 50
}
```

## Persistent STIX IOC store

`common.stix_store.STIXStore` ingests validated generated bundles into SQLite
at `/output/stix_store.sqlite3`. The `iocs` table has a unique constraint on
`(ioc_value, ioc_type)`. A first observation inserts the IOC; later observations
update `last_seen`, the latest source and raw bundle, and atomically increment
`sighting_count` instead of creating duplicate rows. `first_seen` and the
original `stix_id` remain unchanged.

Ingest a generated bundle:

```bash
docker compose run --rm api python -m scripts.ingest_stix \
  /output/stix_bundles/20260802T150200.123456Z.json
```

Inspect the local store:

```bash
docker compose run --rm api python -c \
  "import sqlite3; db=sqlite3.connect('/output/stix_store.sqlite3'); print(db.execute('SELECT ioc_type, ioc_value, sighting_count, first_seen, last_seen FROM iocs').fetchall())"
```

## Sigma rule generation

`common.sigma_rule_generator` reads network IOCs from the SQLite STIX store and
batches them into one Sigma rule per group: IP addresses, domains, and URLs.
IPv4 and IPv6 values use `destination.ip` with firewall logs, domains use
`dns.query.name` with DNS logs, and URL hostnames use `url.domain` with proxy
logs. SHA hashes and other non-network indicators are intentionally excluded.

Rules default to `medium`; a batch becomes `high` when a matching stored STIX
Indicator carries confidence 75 or greater. Existing `attack.*` or
`mitre-attack.*` labels are copied to Sigma tags. Rules are written atomically
as YAML documents to `/output/sigma_rules/{date}.yml`.

```bash
docker compose run --rm api python -m scripts.sigma_rule_generator
```

## YARA rule generation

`common.yara_rule_generator` reads MD5, SHA-1, and SHA-256 IOCs from the SQLite
STIX store and writes one exact-file hash rule block per IOC into a dated YARA
file. Each block is compiled independently with `yara-python`; invalid blocks
are discarded. The combined artifact is compiled once more before an atomic
write to `/output/yara_rules/{date}.yar`.

Hash-only detection is explicitly documented in the generated file as a v1
limitation because even a small file change bypasses an exact hash. The module
keeps rule rendering separate from loading and saving so strings, byte
patterns, PE structure, and behavioral conditions can be added later.

```bash
docker compose run --rm api python -m scripts.yara_rule_generator
```

## SIEM deployment

`common.siem_pusher` selects Splunk, Elastic Security, Wazuh Indexer, or QRadar
through `SIEM_TYPE`. Sigma documents are converted through the matching
pySigma backend and submitted through provider-specific REST payloads. Every
success, failure, or manual-deployment result is stored in the local SQLite
`siem_push_log` table.

Splunk creates a scheduled saved search. Elastic creates a disabled-by-default
Detection Engine query rule. Wazuh creates a disabled-by-default OpenSearch
Alerting monitor on the configured Wazuh Indexer. QRadar AQL conversion is
available through the dynamically loaded optional legacy backend, but that
backend conflicts with current pySigma and should run in an isolated adapter
service. An approved integration endpoint must also be supplied through
`SIEM_RULE_ENDPOINT` because QRadar has no universal correlation-rule creation
endpoint. Without both, the attempt is logged as `manual_required`. YARA is
uploaded only when `SIEM_YARA_ENDPOINT` is explicitly set;
otherwise the artifact is safely logged as `manual_required`.

Configure `.env` and push a generated file:

```bash
docker compose run --rm api python -m scripts.siem_pusher \
  /output/sigma_rules/2026-08-02.yml --type sigma

docker compose run --rm api python -m scripts.siem_pusher \
  /output/yara_rules/2026-08-02.yar --type yara
```

Rules default to disabled until reviewed. Set `SIEM_RULES_ENABLED=true` only
after testing the generated native query against the target telemetry schema.

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
