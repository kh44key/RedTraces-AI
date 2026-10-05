# RedTraces AI source integration guide

RedTraces AI is a single CTI workflow: each source collects only authorized
public or account-authorized content, normalizes it into a finding, extracts
IOCs, applies severity scoring, and exposes the resulting intelligence in the
same analyst dashboard.  The platform labels identify the source; they are not
separate applications.

## Where credentials belong

Create or edit the root `.env` file beside `compose.yaml`.  Docker Compose
passes this file to the X, Instagram, Facebook, Telegram, forum, and Unified
CTI services.  Keep `.env` private; do not commit it or paste its contents in
an issue or chat.

```dotenv
# Enable polling only after the corresponding source has been configured.
ENABLE_LIVE_COLLECTION=false

# X / Twitter: authenticated browser session cookies for the approved account.
X_USERNAME=your_x_username
X_AUTH_TOKEN=replace_with_auth_token_cookie
X_CT0=replace_with_ct0_cookie

# Instagram: an Instaloader session file is preferred.  A password is only a
# fallback when no session file is available.
PKCERT_IG_USER=your_instagram_username
PKCERT_IG_SESSIONFILE=/data/instagram.session
# PKCERT_IG_PASS=only_if_you_choose_password_login

# Facebook: absolute container path to a Netscape-format cookies.txt file.
PKCERT_FB_COOKIES=/data/facebook-cookies.txt

# Existing advanced Telegram pipeline.
TELEGRAM_API_ID=your_numeric_api_id
TELEGRAM_API_HASH=your_api_hash
REDTRACES_TELEGRAM_CHANNELS=approved_public_channel_1,approved_public_channel_2
```

For a preferred Instagram session or Facebook cookies file, copy the file once
into the named collector volume after its container has started:

```powershell
docker cp .\private\instagram.session redtraces-ai-instagram-1:/data/instagram.session
docker cp .\private\facebook-cookies.txt redtraces-ai-facebook-1:/data/facebook-cookies.txt
```

Set `ENABLE_LIVE_COLLECTION=true` only after credentials and monitored sources
are in place. Restart the collectors you configured:

```powershell
docker compose up -d --build twitter instagram facebook telegram redtraces-telegram
```

Use the source-specific API to add monitored profiles, pages, groups, hashtags,
or channels.  Each collector exposes a small operator UI/API on localhost:

| Source | Local endpoint | Purpose |
| --- | --- | --- |
| X / Twitter | `http://localhost:8102` | Manage approved X accounts and review collected findings. |
| Facebook | `http://localhost:8103` | Add approved public pages/groups and review findings. |
| Instagram | `http://localhost:8104` | Add approved public profiles or hashtags and review findings. |
| Telegram | `http://localhost:8101` | Configure the legacy collector; the advanced pipeline feeds the Intelligence Hub. |
| Forums / dark-web intake | `http://localhost:5000/docs` | Submit normalized, reviewed findings to the shared forum feed. |

## Dark-web sources

The local `forums` service is the supported, safe operational path in this
combined Docker stack.  It receives reviewed information from an approved
provider, internal analyst review, or a compliant connector and places it in
the same CTI feed as social-source findings.

Send a finding to `POST http://localhost:5000/api/alerts` with the
`X-API-Key` header set to `UNIFIED_CTI_API_KEY` from `.env`:

```json
{
  "url": "https://approved-source.example/report/123",
  "page_title": "Credential exposure report",
  "content_snippet": "Reviewed report contains a suspicious domain and SHA-256.",
  "matched_keywords": ["credential leak", "malware"],
  "severity": "HIGH",
  "score": 88
}
```

The merged `redtraces-core/collectors/darkweb_collector.py` provides a
separate Tor-based adapter framework for explicitly approved `.onion` sources.
It is intentionally not enabled by the root Docker stack because each source
needs a site-specific parser, owner approval, and a Tor service.  Configure
`DARKWEB_TARGETS`, `TOR_CONTROL_PASSWORD`, and the adapter only after those
requirements are satisfied.  Its README documents that advanced collector.

## Verify the end-to-end flow

1. Open `http://localhost:3000` (or the configured `DASHBOARD_PORT`, such as 3500).
   Select **Live** to use connected data, then choose a source view.
2. Add an approved monitored target in one collector UI.
3. Allow a poll cycle, then review its finding and extracted indicators.
4. Use **Overview**, **IOC explorer**, **Source correlation**, and **STIX store**
   to review loaded indicators, source context, and processed artifacts.

The dashboard defaults to a clearly labelled synthetic Demo workspace. A shared
frontend-only tunnel does not expose the loopback-only collector APIs, so remote
viewers should use Demo mode. Do not expose collector or database ports to share
the presentation.

The current X, Instagram, and Facebook collectors are session-based adapters;
their code does not consume official X or Meta Graph API keys. Do not add those
keys expecting these adapters to use them. A future official-API connector can
be added alongside these adapters if you have an approved developer account.

All collection must comply with the platform's terms, your account permissions,
and applicable law. Use only approved public sources and accounts you control.
