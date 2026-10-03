import asyncio
import json
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import mysql.connector
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from mysql.connector import pooling
from pydantic import BaseModel
from pkcert_config import mysql_config, get_secret
from twscrape import API, gather

from x_account_manager import POOL_DB, pool_status

# =========================================================================
# CONFIGURATION
# =========================================================================
POLL_INTERVAL_SECONDS = 300
TWEETS_PER_BATCH = 20

MYSQL_CONFIG = mysql_config("x_leaks_db")

USERNAME = get_secret("X_USERNAME")
AUTH_TOKEN = get_secret("X_AUTH_TOKEN")
CT0 = get_secret("X_CT0")
# =========================================================================


def create_database_if_not_exists():
    try:
        conn = mysql.connector.connect(
            host=MYSQL_CONFIG["host"],
            port=MYSQL_CONFIG["port"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{MYSQL_CONFIG['database']}`"
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[!] Database Setup Warning: {e}")


create_database_if_not_exists()

db_pool = pooling.MySQLConnectionPool(
    pool_name="mysql_pool", pool_size=5, **MYSQL_CONFIG
)


def get_db_connection():
    return db_pool.get_connection()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS x_leaks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tweet_id VARCHAR(64) UNIQUE,
            author_id VARCHAR(64),
            author_username VARCHAR(255),
            detected_domains JSON,
            detected_entities JSON,
            severity VARCHAR(32) DEFAULT 'High',
            text TEXT,
            tweet_date VARCHAR(64),
            processed_at VARCHAR(64)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    try:
        cursor.execute(
            "ALTER TABLE x_leaks ADD COLUMN severity VARCHAR(32) DEFAULT"
            " 'High';"
        )
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitored_channels (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            added_at VARCHAR(64) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    conn.commit()
    cursor.close()
    conn.close()


init_db()

# =========================================================================
# INDICATORS & THREAT CATEGORIZATION
# =========================================================================
GOVT_ENTITY_INDICATORS = list(
    set([
        "gov.pk",
        "gop.pk",
        "mil.pk",
        "government",
        "govt",
        "ministry",
        "cabinet",
        "public sector",
        "national database",
        "vehicle registration",
        "transportation",
        "nadra",
        "fia",
        "pta",
        "fbr",
        "hec",
        "secp",
        "sbp",
        "state bank",
        "pak army",
        "pak navy",
        "paf",
        "isi",
        "cnic",
        "passport",
        "punjab",
        "sindh",
        "kpk",
        "balochistan",
        "islamabad",
        "lahore",
        "karachi",
        "peshawar",
        "quetta",
        "نادرا",
        "پاک فوج",
        "پاک فضائیہ",
        "پاک بحریہ",
        "حکومت پاکستان",
        "حکومت",
    ])
)

BIG_PRIVATE_ENTITY_INDICATORS = list(
    set([
        "jazz",
        "zong",
        "telenor",
        "ufone",
        "ptcl",
        "nayatel",
        "kelectric",
        "lesco",
        "gepco",
        "mepco",
        "fesco",
        "meezan bank",
        "hbl",
        "ubl",
        "mcb",
        "abl",
        "bank alfalah",
        "easypaisa",
        "jazzcash",
        "nust",
        "fast nu",
        "lums",
        "uol",
        "giki",
        "comsats",
    ])
)

PAKISTAN_ENTITY_INDICATORS = list(
    set(
        GOVT_ENTITY_INDICATORS
        + BIG_PRIVATE_ENTITY_INDICATORS
        + ["pakistan", "pakistani"]
    )
)

# Specific compound threat phrases avoid matching harmless uses of words such
# as "leak", "breach", or "database" by themselves.
EXPLICIT_CYBER_ACTIONS = [
    "data leak",
    "database leak",
    "db leak",
    "data breach",
    "database breach",
    "hacked db",
    "hacked database",
    "selling access",
    "selling db",
    "selling data",
    "data for sale",
    "access for sale",
    "combolist",
    "stealer log",
    "stealer logs",
    "exfiltrated",
    "root access",
    "sql dump",
    "db dump",
    "defaced by",
    "pwned by",
    "unauthorized access",
    "darkweb",
    "dark web",
    "wso webshell",
    "b374k",
    "c99shell",
    "de-face.txt",
    "hacked.txt",
    "ہیک کر دیا",
    "ڈیٹا لیک",
    "ڈیٹا چوری",
    "ہیکرز",
]

EXCLUDE_WORDS = [
    "neet",
    "rahul gandhi",
    "republic",
    "paper leak",
    "exam leak",
    "student",
    "education",
    "nta",
    "upsc",
    "cbse",
    "mppsc",
    "bihar",
    "delhi",
    "india",
    "paper leaks",
    "exam",
    "question paper",
    "ratta baaz",
    "patwari",
    "hiring",
    "vacancy",
    "job",
    "technician",
    "salaries",
    "recruitment",
    "career",
    "script",
    "movie",
    "dhurander",
    "funny",
    "lol",
    "rainfall",
    "rain",
    "inundating",
    "heavy rainfall",
]

# Filtering out routine news, regulatory penalties, and policy news
IGNORE_WORDS = [
    "imposes fine",
    "slaps fine",
    "fined",
    "fine on",
    "geo-fencing breach",  # regulatory policy breach, not a cyber data breach
    "sim geo-fencing",
    "marital status",
    "app mobile",
    "pakid",
    "air force one",
    "decoy",
    "assassination threat",
    "according to data",
    "official data",
    "weather data",
    "economic data",
    "data analysis",
    "file a report",
    "public record",
    "data collection",
    "data entry",
    "categorically rejected",
    "taken notice of",
    "denies claims",
    "false reports",
    "breach of international",
    "breach of law",
    "breach of obligations",
    "breach of contract",
    "ceasefire breach",
    "ceasefire breaches",
    "lab leak",
    "super injunction",
    "crude oil",
    "oil pipeline",
    "pipeline leak",
    "gas leak",
    "water leak",
    "video leak",
    "pics leak",
    "movie leak",
    "spoiler",
]


def analyze_text(text: str):
    if not text:
        return False, [], [], "Low"

    text_lower = text.lower()

    # 1. Immediate rejection of false-positive noise and news advisories
    if any(exclude in text_lower for exclude in EXCLUDE_WORDS):
        return False, [], [], "Low"
    if any(ignore in text_lower for ignore in IGNORE_WORDS):
        return False, [], [], "Low"

    # 2. Require a specific cyber action.
    has_cyber_action = any(
        action in text_lower for action in EXPLICIT_CYBER_ACTIONS
    )

    # Single-word terms qualify only when paired with technical exposure data.
    if not has_cyber_action and (
        "breach" in text_lower or "hacked" in text_lower
    ):
        has_cyber_action = any(
            tech in text_lower
            for tech in [
                ".gov.pk",
                ".mil.pk",
                "server",
                "credentials",
                "admin access",
            ]
        )

    if not has_cyber_action:
        return False, [], [], "Low"

    # 3. Match target domains and entities.
    domain_pattern = r"\b[a-zA-Z0-9.-]+\.(?:gov|pk|gov\.pk|mil\.pk)\b"
    matched_domains = re.findall(domain_pattern, text_lower)
    matched_entities = [
        e for e in PAKISTAN_ENTITY_INDICATORS if e in text_lower
    ]
    # Rule: Must reference Pakistan, a Pakistani entity, or a .pk domain
    if not (matched_domains or matched_entities or "pakistan" in text_lower):
        return False, [], [], "Low"

    # 3. Determine Priority Level
    is_govt_related = (
        any(
            d.endswith((".gov.pk", ".gop.pk", ".gov", ".mil.pk"))
            for d in matched_domains
        )
        or any(e in GOVT_ENTITY_INDICATORS for e in matched_entities)
        or "government" in text_lower
        or "govt" in text_lower
        or "cnic" in text_lower
    )

    if is_govt_related:
        severity = "High"
    elif any(e in BIG_PRIVATE_ENTITY_INDICATORS for e in matched_entities):
        severity = "Moderate"
    else:
        severity = "Low"

    return True, list(set(matched_domains)), list(set(matched_entities)), severity


def save_matched_leak(data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT IGNORE INTO x_leaks (
                tweet_id, author_id, author_username, detected_domains,
                detected_entities, severity, text, tweet_date, processed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                data["tweet_id"],
                data["author_id"],
                data["author_username"],
                json.dumps(data["detected_domains"]),
                json.dumps(data["detected_entities"]),
                data.get("severity", "High"),
                data["text"],
                str(data["tweet_date"]),
                str(data["processed_at"]),
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Database Error] Failed to save tweet: {e}")


def handle_tweet(tweet_id, author_id, author_username, text, created_at):
    is_alert, domains_found, entities_found, severity = analyze_text(text)
    if not is_alert:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    tweet_date_str = (
        created_at.isoformat()
        if isinstance(created_at, datetime)
        else str(created_at or now_iso)
    )

    record = {
        "tweet_id": str(tweet_id),
        "author_id": str(author_id) if author_id else "unknown",
        "author_username": author_username or "unknown",
        "detected_domains": domains_found,
        "detected_entities": entities_found,
        "severity": severity,
        "text": text,
        "tweet_date": tweet_date_str,
        "processed_at": now_iso,
    }
    print(
        f"\n[!] ALERT [{severity} SEVERITY]: POTENTIAL EXPOSURE ->"
        f" @{record['author_username']}: {text[:100]}..."
    )
    save_matched_leak(record)


# =========================================================================
# TWSCRAPE BACKGROUND WORKER
# =========================================================================
def get_monitored_channels_from_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM monitored_channels")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r["username"] for r in rows]
    except Exception as e:
        print(f"[!] Error fetching channels: {e}")
        return []


async def run_twscrape_poll():
    # Shared pool file, so accounts added with add_x_account.py are picked up
    api = API(POOL_DB)
    cookie_str = f"auth_token={AUTH_TOKEN}; ct0={CT0}"

    try:
        if USERNAME and AUTH_TOKEN and CT0:
            await api.pool.add_account_cookies(USERNAME, cookie_str)
        print(f"[+] Account '{USERNAME}' cookies synchronized.")
    except Exception as e:
        print(f"[*] Cookie sync note: {e}")

    # twscrape rotates requests across every active account on its own
    accounts = await api.pool.get_all()
    active = [a for a in accounts if a.active]
    print(
        f"[+] X worker pool: {len(active)}/{len(accounts)} account(s) active."
    )
    if len(accounts) == 1:
        print("[*] Add more with:  python add_x_account.py add")

    search_queries = [
        '(pakistan OR "gov.pk" OR nadra OR fbr) ("data leak" OR "data breach" OR'
        ' "database leak" OR "selling db" OR "combolist") -neet -exam -"paper'
        ' leak"'
    ]

    print("[+] Zero-cost TWSCRAPE monitor active...")

    while True:
        for query in search_queries:
            try:
                tweets = await gather(
                    api.search(query, limit=TWEETS_PER_BATCH)
                )
                for tweet in tweets:
                    handle_tweet(
                        tweet_id=tweet.id,
                        author_id=tweet.user.id,
                        author_username=tweet.user.username,
                        text=tweet.rawContent,
                        created_at=tweet.date,
                    )
            except Exception as e:
                print(f"[twscrape search info] Notice: {e}")

        target_users = get_monitored_channels_from_db()
        for target_user in target_users:
            try:
                user_info = await api.user_by_login(target_user)
                if user_info:
                    tweets = await gather(
                        api.user_tweets(user_info.id, limit=TWEETS_PER_BATCH)
                    )
                    for tweet in tweets:
                        handle_tweet(
                            tweet_id=tweet.id,
                            author_id=tweet.user.id,
                            author_username=tweet.user.username,
                            text=tweet.rawContent,
                            created_at=tweet.date,
                        )
            except Exception as e:
                print(f"[twscrape channel info] Target @{target_user}: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_twscrape_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_twscrape_poll())


# =========================================================================
# FASTAPI APP & API ENDPOINTS
# =========================================================================
_bg_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bg_thread
    _bg_thread = threading.Thread(target=start_twscrape_loop, daemon=True)
    if os.getenv("ENABLE_LIVE_COLLECTION", "false").lower() == "true":
        _bg_thread.start()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AddKeywordRequest(BaseModel):
    term: str


class AddChannelRequest(BaseModel):
    username: str


def clean_row_json(row):
    for field in ["detected_domains", "detected_entities"]:
        if isinstance(row.get(field), str):
            try:
                row[field] = json.loads(row[field])
            except Exception:
                row[field] = []
        elif row.get(field) is None:
            row[field] = []
    return row


@app.post("/upload-file")
async def upload_file(request: Request, filename: str = "file_upload.txt"):
    try:
        contents = await request.body()
        text_data = contents.decode("utf-8", errors="ignore")
        detected_count = 0

        blocks = text_data.split("\n\n")

        for idx, block in enumerate(blocks):
            block_str = block.strip()
            if not block_str:
                continue

            is_alert, domains, entities, severity = analyze_text(block_str)
            if is_alert:
                handle_tweet(
                    tweet_id=f"file_{int(datetime.now().timestamp())}_{idx}",
                    author_id="uploaded_file",
                    author_username=filename,
                    text=block_str,
                    created_at=datetime.now(timezone.utc),
                )
                detected_count += 1

        return {
            "status": "success",
            "file": filename,
            "blocks_processed": len(blocks),
            "leaks_detected": detected_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"File processing error: {e}"
        )


@app.post("/add-keyword")
async def add_keyword(req: AddKeywordRequest):
    term = req.term.strip().lower()
    if not term:
        raise HTTPException(400, "Empty term.")
    if term not in PAKISTAN_ENTITY_INDICATORS:
        PAKISTAN_ENTITY_INDICATORS.append(term)
    return {"status": "ok", "watching": len(PAKISTAN_ENTITY_INDICATORS)}


@app.post("/add-channel")
async def add_channel(req: AddChannelRequest):
    username = req.username.strip().replace("@", "").lower()
    if not username:
        raise HTTPException(400, "Empty username.")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT IGNORE INTO monitored_channels (username, added_at) VALUES"
            " (%s, %s)",
            (username, now_iso),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "channel": username}
    except Exception as e:
        raise HTTPException(500, f"Database failure: {e}")


@app.get("/accounts")
async def list_accounts():
    """Live status of every X account twscrape rotates between."""
    try:
        return await pool_status()
    except Exception as e:
        raise HTTPException(500, f"Failed reading the X account pool: {e}")


@app.get("/channels")
async def list_channels():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, added_at FROM monitored_channels ORDER BY id"
            " DESC"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if os.getenv("ENABLE_LIVE_COLLECTION", "false").lower() == "true":
            rows.insert(0, {"id": "global-search", "username": "Global Pakistan Threat Search", "source_type": "system"})
        return rows
    except Exception as e:
        raise HTTPException(500, f"Database query failed: {e}")


@app.delete("/remove-channel")
async def remove_channel(username: str):
    user_clean = username.strip().replace("@", "").lower()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM monitored_channels WHERE username = %s", (user_clean,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "removed": user_clean}
    except Exception as e:
        raise HTTPException(500, f"Failed to remove channel: {e}")


@app.get("/leaks")
async def list_leaks(limit: int = 5000):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM x_leaks ORDER BY id DESC LIMIT %s", (limit,)
        )
        rows = cursor.fetchall()
        rows = [clean_row_json(r) for r in rows]
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Database query failed: {e}")


@app.get("/search-leaks")
async def search_leaks(
    keyword: str = Query("", description="Simple keyword to filter database"),
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if not keyword.strip():
            cursor.execute("SELECT * FROM x_leaks ORDER BY id DESC LIMIT 500")
        else:
            search_param = f"%{keyword.strip()}%"
            query_sql = """
                SELECT * FROM x_leaks 
                WHERE text LIKE %s 
                   OR author_username LIKE %s 
                   OR detected_entities LIKE %s 
                   OR detected_domains LIKE %s 
                   OR severity LIKE %s
                ORDER BY id DESC
            """
            cursor.execute(
                query_sql,
                (
                    search_param,
                    search_param,
                    search_param,
                    search_param,
                    search_param,
                ),
            )

        rows = cursor.fetchall()
        rows = [clean_row_json(r) for r in rows]
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Search failed: {e}")


@app.get("/leaks-by-date")
async def get_leaks_by_date():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM x_leaks ORDER BY id DESC")
        rows = cursor.fetchall()
        rows = [clean_row_json(r) for r in rows]

        now = datetime.now(timezone.utc)
        today_leaks = []
        week_leaks = []

        for row in rows:
            try:
                date_val = row.get("tweet_date") or row.get("processed_at")
                tweet_dt = datetime.fromisoformat(
                    str(date_val).replace("Z", "+00:00")
                )
                days_diff = (now - tweet_dt).days
                if days_diff == 0:
                    today_leaks.append(row)
                if days_diff <= 7:
                    week_leaks.append(row)
            except Exception:
                week_leaks.append(row)

        cursor.close()
        conn.close()

        return {
            "today": today_leaks,
            "this_week": week_leaks,
            "all_time": rows,
        }
    except Exception as e:
        raise HTTPException(500, f"Date grouping failed: {e}")


# =========================================================================
# FRONTEND DASHBOARD
# =========================================================================
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    return r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>X Watch — Threat Intelligence</title>
  <style>
    :root{--bg:#000;--panel:#000;--line:#2f3336;--soft:#16181c;--text:#e7e9ea;--muted:#71767b;--blue:#1d9bf0;--red:#f4212e;--green:#00ba7c;--amber:#f59e0b}
    *{box-sizing:border-box}html{color-scheme:dark}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
    button,input,select{font:inherit}button{color:inherit}.shell{width:min(1265px,100%);margin:auto;display:grid;grid-template-columns:260px minmax(0,600px) 350px;min-height:100vh}
    .left{position:sticky;top:0;height:100vh;padding:12px 20px;border-right:1px solid var(--line)}.brand{width:52px;height:52px;display:grid;place-items:center;font-size:30px;font-weight:800;border-radius:50%}.brand:hover,.nav-btn:hover,.icon-btn:hover{background:#181818}
    nav{margin-top:8px}.nav-btn{width:max-content;max-width:100%;display:flex;align-items:center;gap:18px;border:0;background:transparent;border-radius:999px;padding:12px 16px;margin:3px 0;cursor:pointer;font-size:20px;text-align:left}.nav-btn.active{font-weight:700}.nav-icon{width:25px;text-align:center}.post-btn{width:90%;margin-top:14px;border:0;background:var(--blue);font-weight:700;font-size:17px;padding:15px;border-radius:999px;cursor:pointer}.post-btn:hover{background:#1a8cd8}.system-card{position:absolute;bottom:18px;left:20px;right:20px;display:flex;align-items:center;gap:10px;padding:10px;border-radius:999px}.pulse{width:10px;height:10px;border-radius:50%;background:var(--green);box-shadow:0 0 0 5px #00ba7c20}.system-card small{display:block;color:var(--muted)}
    main{min-width:0;border-right:1px solid var(--line)}.topbar{position:sticky;top:0;z-index:5;background:#000d;border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}.title-row{height:53px;display:flex;align-items:center;justify-content:space-between;padding:0 16px}.title-row h1{font-size:20px;margin:0}.icon-btn{border:0;background:transparent;width:38px;height:38px;border-radius:50%;cursor:pointer;font-size:18px}.tabs{display:flex}.tab{flex:1;border:0;background:transparent;color:var(--muted);font-weight:600;height:48px;cursor:pointer;position:relative}.tab:hover{background:#181818}.tab.active{color:var(--text)}.tab.active:after{content:"";position:absolute;height:4px;border-radius:4px;background:var(--blue);left:25%;right:25%;bottom:0}
    .composer{display:flex;gap:12px;padding:13px 16px;border-bottom:1px solid var(--line)}.avatar{flex:0 0 42px;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#1d9bf0,#7b2cbf);font-weight:800;color:#fff}.composer-copy{flex:1}.composer-title{font-size:20px;margin:4px 0 2px}.composer-sub{color:var(--muted)}.filter-bar{padding:10px 16px;border-bottom:1px solid var(--line);display:flex;gap:8px;overflow:auto}.chip{border:1px solid var(--line);background:transparent;border-radius:999px;padding:7px 13px;white-space:nowrap;cursor:pointer}.chip.active,.chip:hover{border-color:var(--blue);color:var(--blue)}
    .notice{padding:32px 20px;text-align:center;color:var(--muted);border-bottom:1px solid var(--line)}.spinner{display:inline-block;width:22px;height:22px;border:3px solid var(--line);border-top-color:var(--blue);border-radius:50%;animation:spin .7s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
    .tweet{display:flex;gap:11px;padding:12px 16px;border-bottom:1px solid var(--line);transition:.15s}.tweet:hover{background:#080808}.tweet-body{min-width:0;flex:1}.meta{display:flex;gap:6px;align-items:center;min-width:0;flex-wrap:wrap}.name{font-weight:700}.handle,.dot,.time{color:var(--muted)}.handle{overflow:hidden;text-overflow:ellipsis}.content{margin:6px 0 10px;white-space:pre-wrap;overflow-wrap:anywhere}.indicators{display:flex;flex-wrap:wrap;gap:6px}.tag{font-size:12px;border-radius:999px;padding:3px 9px;background:#1d9bf020;color:#65baf3;border:1px solid #1d9bf055}.tag.domain{background:#f4212e18;color:#ff7a84;border-color:#f4212e55}.actions{display:flex;justify-content:space-between;color:var(--muted);margin-top:11px;max-width:390px;font-size:13px}.action{display:flex;gap:7px;align-items:center}.id-pill{background:var(--soft);color:var(--muted);padding:2px 7px;border-radius:10px;font-size:11px}
    .severity-badge{font-size:11px;font-weight:700;border-radius:999px;padding:2px 8px;text-transform:uppercase;margin-left:auto}
    .severity-badge.high{background:#f4212e25;color:#ff525e;border:1px solid #f4212e66}
    .severity-badge.moderate{background:#f59e0b25;color:#fbbf24;border:1px solid #f59e0b66}
    .severity-badge.low{background:#00ba7c25;color:#34d399;border:1px solid #00ba7c66}
    .channel-item{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line)}.channel-item:hover{background:#080808}.btn-danger{background:#f4212e20;color:#ff7a84;border:1px solid #f4212e55;padding:5px 12px;border-radius:999px;cursor:pointer}.btn-danger:hover{background:#f4212e;color:#fff}
    .panel{display:none}.panel.active{display:block}.section-head{padding:12px 16px;border-bottom:1px solid var(--line);font-weight:700;display:flex;justify-content:space-between}.count{color:var(--blue)}
    .search-wrap{padding:12px 16px;border-bottom:1px solid var(--line)}.search-actions{display:flex}.search-box{display:flex;background:#202327;border:1px solid transparent;border-radius:999px;overflow:hidden}.search-box:focus-within{background:#000;border-color:var(--blue)}.search-box span{padding:11px 0 11px 16px;color:var(--muted)}.search-box input{width:100%;border:0;outline:0;background:transparent;color:var(--text);padding:11px}.primary{border:0;background:var(--blue);font-weight:700;border-radius:999px;padding:9px 18px;cursor:pointer;margin-left:8px}.empty{padding:50px 28px;text-align:center}.empty h2{font-size:28px;margin:0 0 8px}.empty p{color:var(--muted);margin:auto;max-width:350px}
    .right{padding:12px 0 30px 28px}.right-inner{position:sticky;top:12px}.side-search{display:flex;align-items:center;background:#202327;border-radius:999px;padding:0 16px;margin-bottom:16px}.side-search input{width:100%;border:0;outline:0;background:transparent;padding:12px;color:var(--text)}.side-card{border:1px solid var(--line);border-radius:16px;margin-bottom:16px;overflow:hidden}.side-card h2{font-size:20px;margin:0;padding:12px 16px}.trend{padding:11px 16px;cursor:pointer}.trend:hover{background:#080808}.trend small{color:var(--muted)}.trend strong{display:block;margin:2px 0}.show-more{padding:15px 16px;color:var(--blue);cursor:pointer}.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line)}.stat{background:#000;padding:15px}.stat b{font-size:22px;display:block}.stat span{color:var(--muted);font-size:13px}
    dialog{width:min(520px,calc(100% - 24px));border:1px solid var(--line);border-radius:16px;background:#000;color:var(--text);padding:0}dialog::backdrop{background:#5b708366}.modal-head{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid var(--line)}.modal-head h2{font-size:20px;margin:0}.modal-body{padding:20px}.modal-body label{font-weight:700;display:block;margin-bottom:8px}.modal-body input,.modal-body select{width:100%;border:1px solid var(--line);border-radius:10px;background:#000;color:var(--text);padding:14px;outline:0;margin-bottom:12px}.modal-body input:focus,.modal-body select:focus{border-color:var(--blue)}.modal-body p{color:var(--muted);font-size:13px}.modal-foot{display:flex;justify-content:flex-end;padding-top:10px}.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);opacity:0;background:var(--blue);color:white;padding:12px 20px;border-radius:8px;transition:.2s;z-index:20}.toast.show{transform:translateX(-50%) translateY(0);opacity:1}
  </style>
</head>
<body>
<div class="shell">
  <aside class="left">
    <div class="brand">𝕏</div>
    <nav>
      <button class="nav-btn active" data-panel="live"><span class="nav-icon">⌂</span><span class="nav-label">Live feed</span></button>
      <button class="nav-btn" data-panel="database"><span class="nav-icon">▤</span><span class="nav-label">Archive</span></button>
      <button class="nav-btn" data-panel="search"><span class="nav-icon">⌕</span><span class="nav-label">Explore</span></button>
      <button class="nav-btn" data-panel="date"><span class="nav-icon">◷</span><span class="nav-label">Timeline</span></button>
      <button class="nav-btn" data-panel="targets"><span class="nav-icon">◎</span><span class="nav-label">Targets</span></button>
    </nav>
    <button class="post-btn" onclick="openTargetModal()">Add target</button>
    <div class="system-card"><span class="pulse"></span><div><b>Monitor active</b><small>Scanning X in real time</small></div></div>
  </aside>

  <main>
    <header class="topbar">
      <div class="title-row"><h1 id="pageTitle">Home</h1><button class="icon-btn" onclick="refreshCurrent()">↻</button></div>
      <div class="tabs" id="feedTabs">
        <button class="tab active" data-filter="all">For you</button><button class="tab" data-filter="domains">Domains</button>
        <button class="tab" data-filter="entities">Entities</button><button class="tab" data-filter="recent">Latest</button>
      </div>
    </header>
    <section class="panel active" id="livePanel">
      <div class="composer"><div class="avatar">XW</div><div class="composer-copy"><div class="composer-title">Threat Intelligence Feed</div><div class="composer-sub">Verified exposure signals detected from public and private accounts</div></div></div>
      <div id="liveFeed"><div class="notice"><span class="spinner"></span><div>Loading monitored posts…</div></div></div>
    </section>
    <section class="panel" id="databasePanel"><div class="section-head"><span>Complete alert archive</span><span class="count"><span id="dbRecordCount">0</span> records</span></div><div id="databaseFeed"></div></section>
    <section class="panel" id="searchPanel">
      <div class="search-wrap"><div class="search-actions"><div class="search-box" style="flex:1"><span>⌕</span><input id="simpleKeyword" placeholder="Search posts, accounts, domains, targets, or severity (high, moderate, low)" autocomplete="off"></div><button class="primary" onclick="executeKeywordSearch()">Search</button></div></div>
      <div id="searchFeed"><div class="empty"><h2>Search the archive</h2><p>Find monitored posts by keyword, account, target entity, affected domain, or priority level.</p></div></div>
    </section>
    <section class="panel" id="datePanel"><div class="filter-bar"><button class="chip active" data-date="today">Today</button><button class="chip" data-date="week">This week</button><button class="chip" data-date="all">All time</button></div><div id="dateFeed"></div></section>
    <section class="panel" id="targetsPanel">
      <div class="section-head"><span>Monitored Private/Public Channels</span><button class="primary" onclick="openTargetModal()">+ Add Target</button></div>
      <div id="channelsList"><div class="notice"><span class="spinner"></span></div></div>
      <div class="empty" style="border-top:1px solid var(--line)">
        <div class="avatar" style="margin:0 auto 16px">📂</div>
        <h2>Scan Local Dump File</h2>
        <p>Upload a line-by-line text or raw data file to detect threat exposures locally.</p>
        <input type="file" id="fileInput" style="display:none" onchange="uploadFile(this)">
        <button class="primary" style="margin-top:20px" onclick="document.getElementById('fileInput').click()">Upload File</button>
      </div>
    </section>
  </main>

  <aside class="right"><div class="right-inner">
    <div class="side-search"><span>⌕</span><input id="quickSearch" placeholder="Search X Watch"></div>
    <section class="side-card"><h2>Monitor overview</h2><div class="stat-grid"><div class="stat"><b id="liveCount">—</b><span>Recent alerts</span></div><div class="stat"><b id="todayCount">—</b><span>Today</span></div><div class="stat"><b id="weekCount">—</b><span>This week</span></div><div class="stat"><b><span class="pulse" style="display:inline-block"></span> Live</b><span>Scraper status</span></div></div></section>
    <section class="side-card"><h2>Worker accounts</h2><div id="accountsList"><p style="opacity:.6;font-size:13px">Loading accounts…</p></div><p style="opacity:.6;font-size:12px;margin-top:10px;line-height:1.5">twscrape rotates requests across every active account. Add more with <code>python add_x_account.py add</code>.</p></section>
  </div></aside>
</div>

<dialog id="targetModal"><div class="modal-head"><button class="icon-btn" onclick="targetModal.close()">×</button><h2>Add Monitored Target</h2><span style="width:38px"></span></div><div class="modal-body">
  <label for="targetType">Target Type</label>
  <select id="targetType">
    <option value="channel">Private / Public Account Username</option>
    <option value="keyword">Entity Keyword</option>
  </select>
  <label for="newTargetValue">Target Handle or Term</label>
  <input id="newTargetValue" placeholder="e.g. username_or_term" autocomplete="off">
  <div class="modal-foot"><button class="primary" onclick="submitTarget()">Start monitoring</button></div>
</div></dialog>
<div class="toast" id="toast"></div>

<script>
  const state={live:[],database:[],channels:[],dates:{today:[],this_week:[],all_time:[]},feedFilter:'all',dateFilter:'today',panel:'live'};
  const titles={live:'Home',database:'Archive',search:'Explore',date:'Timeline',targets:'Targets'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function formatDate(v){if(!v)return 'Unknown time';const d=new Date(v);if(isNaN(d))return esc(v);const delta=Math.floor((Date.now()-d)/1000);if(delta<60)return 'now';if(delta<3600)return Math.floor(delta/60)+'m';if(delta<86400)return Math.floor(delta/3600)+'h';return d.toLocaleDateString()}
  function avatarColor(name){let h=0;for(const c of String(name))h=(h*31+c.charCodeAt(0))%360;return `hsl(${h} 65% 45%)`}
  function postCard(leak,showId=false){
    const user=leak.author_username||'unknown',entities=leak.detected_entities||[],domains=leak.detected_domains||[],severity=leak.severity||'High',initial=user.slice(0,2).toUpperCase();
    return `<article class="tweet"><div class="avatar" style="background:${avatarColor(user)}">${esc(initial)}</div><div class="tweet-body"><div class="meta"><span class="name">${esc(user)}</span><span class="handle">@${esc(user)}</span><span class="dot">·</span><span class="time">${formatDate(leak.tweet_date||leak.processed_at)}</span>${showId?`<span class="id-pill">#${esc(leak.id)}</span>`:''}<span class="severity-badge ${esc(severity.toLowerCase())}">${esc(severity)} Priority</span></div><div class="content">${esc(leak.text||'')}</div><div class="indicators">${entities.map(x=>`<span class="tag">◎ ${esc(x)}</span>`).join('')}${domains.map(x=>`<span class="tag domain">↗ ${esc(x)}</span>`).join('')}</div></article>`
  }
  function renderFeed(el,rows,showId=false,empty='No monitored posts found.'){el.innerHTML=rows.length?rows.map(x=>postCard(x,showId)).join(''):`<div class="empty"><h2>Nothing here yet</h2><p>${empty}</p></div>`}
  async function getJSON(url){const r=await fetch(url);if(!r.ok)throw new Error('Request failed');return r.json()}
  function fail(el){el.innerHTML='<div class="empty"><h2>Unable to load feed</h2><p>Check database connection, then refresh.</p></div>'}
  async function loadLiveAlerts(){try{state.live=await getJSON('/leaks?limit=50');liveCount.textContent=state.live.length;applyFeedFilter()}catch(e){fail(liveFeed)}}
  function applyFeedFilter(){let rows=state.live;if(state.feedFilter==='domains')rows=rows.filter(x=>(x.detected_domains||[]).length);if(state.feedFilter==='entities')rows=rows.filter(x=>(x.detected_entities||[]).length);renderFeed(liveFeed,rows)}
  async function loadFullDatabase(){databaseFeed.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{state.database=await getJSON('/leaks?limit=5000');dbRecordCount.textContent=state.database.length;renderFeed(databaseFeed,state.database,true)}catch(e){fail(databaseFeed)}}
  async function loadChannels(){channelsList.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{state.channels=await getJSON('/channels');renderChannels()}catch(e){fail(channelsList)}}
  function renderChannels(){if(!state.channels.length){channelsList.innerHTML='<div class="notice">No targets configured.</div>';return}channelsList.innerHTML=state.channels.map(c=>`<div class="channel-item"><div><strong>@${esc(c.username)}</strong></div><button class="btn-danger" onclick="removeChannel('${esc(c.username)}')">Remove</button></div>`).join('')}
  async function removeChannel(user){if(confirm(`Remove @${user}?`)){await fetch('/remove-channel?username='+encodeURIComponent(user),{method:'DELETE'});loadChannels()}}
  async function executeKeywordSearch(){const q=simpleKeyword.value.trim();searchFeed.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{const rows=await getJSON('/search-leaks?keyword='+encodeURIComponent(q));renderFeed(searchFeed,rows)}catch(e){fail(searchFeed)}}
  async function loadDateTables(){dateFeed.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{state.dates=await getJSON('/leaks-by-date');todayCount.textContent=state.dates.today.length;weekCount.textContent=state.dates.this_week.length;applyDateFilter()}catch(e){fail(dateFeed)}}
  function applyDateFilter(){const key=state.dateFilter==='week'?'this_week':state.dateFilter==='all'?'all_time':'today';renderFeed(dateFeed,state.dates[key]||[])}
  function switchPanel(name){state.panel=name;document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));document.getElementById(name+'Panel').classList.add('active');document.querySelectorAll('.nav-btn').forEach(x=>x.classList.toggle('active',x.dataset.panel===name));pageTitle.textContent=titles[name];if(name==='database'&&!state.database.length)loadFullDatabase();if(name==='date')loadDateTables();if(name==='targets')loadChannels()}
  function refreshCurrent(){if(state.panel==='live')loadLiveAlerts();if(state.panel==='database')loadFullDatabase();if(state.panel==='date')loadDateTables();if(state.panel==='search')executeKeywordSearch();if(state.panel==='targets')loadChannels()}
  function openTargetModal(){targetModal.showModal()}
  async function submitTarget(){const type=targetType.value,val=newTargetValue.value.trim();if(!val)return;const endpoint=type==='channel'?'/add-channel':'/add-keyword';await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(type==='channel'?{username:val}:{term:val})});targetModal.close();newTargetValue.value='';if(state.panel==='targets')loadChannels()}
  async function uploadFile(input){if(!input.files||!input.files[0])return;const fd=new FormData();fd.append('file',input.files[0]);try{const r=await fetch('/upload-file',{method:'POST',body:fd});const res=await r.json();alert(`Processed! ${res.leaks_detected} threat leaks detected.`);refreshCurrent();}catch(e){alert('Error processing file.');}}
  document.querySelectorAll('.nav-btn').forEach(b=>b.addEventListener('click',()=>switchPanel(b.dataset.panel)));
  document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-filter]').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.feedFilter=b.dataset.filter;applyFeedFilter()}));
  document.querySelectorAll('[data-date]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-date]').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.dateFilter=b.dataset.date;applyDateFilter()}));
  simpleKeyword.addEventListener('keydown',e=>{if(e.key==='Enter')executeKeywordSearch()});
  async function loadAccounts(){
    const COLORS={online:'#4ade80',cooling:'#fbbf24',error:'#f87171',inactive:'#94a3b8'};
    try{
      const accounts=await getJSON('/accounts');
      if(!accounts.length){accountsList.innerHTML='<p style="opacity:.6;font-size:13px">No accounts registered.</p>';return}
      accountsList.innerHTML=accounts.map(a=>`
        <div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.07)">
          <span style="width:8px;height:8px;border-radius:50%;background:${COLORS[a.status]||'#94a3b8'};flex:none"></span>
          <b style="flex:1;font-size:13px">@${a.username}</b>
          <span style="font-size:11px;opacity:.7;text-transform:uppercase">${a.status}</span>
        </div>
        ${a.note?`<div style="font-size:11px;opacity:.55;padding:0 0 6px 16px">${a.note}</div>`:''}
      `).join('');
    }catch(e){accountsList.innerHTML='<p style="opacity:.6;font-size:13px">Unable to load accounts.</p>'}
  }
  loadLiveAlerts();loadDateTables();loadAccounts();setInterval(loadLiveAlerts,15000);setInterval(loadAccounts,30000);
</script>
</body>
</html>
    """


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8102, reload=False)




