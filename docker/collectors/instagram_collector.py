"""Instagram threat-intelligence collector for RedTraces AI.

Same architecture as the X / Facebook collectors: a FastAPI service polling
monitored sources on a background thread, classifying every caption with the
shared Pakistan cyber-threat ruleset, and storing matches in MySQL. The unified
:3000 dashboard consumes the identical REST shape, so Instagram plugs in exactly
like the other social modules.

Crawler backend: `instaloader`. Monitored targets are Instagram usernames
(public profiles) or hashtags (prefix a target with '#'). Optional login for
better reach is read from .pkcert.env:
    PKCERT_IG_USER         = your instagram username
    PKCERT_IG_SESSIONFILE  = path to an instaloader session file (preferred), OR
    PKCERT_IG_PASS         = password (used only if no session file is present)
If instaloader is missing or login fails, the API still serves and file uploads
still classify — the crawler simply reports offline, mirroring the X collector.
"""

import json
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from itertools import islice

import mysql.connector
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from mysql.connector import pooling
from pydantic import BaseModel

from pkcert_config import mysql_config, load_private_settings
from threat_indicators import analyze_text, PAKISTAN_ENTITY_INDICATORS
from collector_ui import dashboard_html

# =========================================================================
# CONFIGURATION
# =========================================================================
POLL_INTERVAL_SECONDS = 300
POSTS_PER_TARGET = 12
PLATFORM = "INSTAGRAM"

# Reuses the now-unused telegram_leaks_db (pkcert already has full grants on it)
# with Instagram-specific tables, so no MySQL-root DB creation is needed.
MYSQL_CONFIG = mysql_config("instagram_leaks_db")

_settings = load_private_settings()
IG_USER = _settings.get("PKCERT_IG_USER", "").strip() or None
IG_PASS = _settings.get("PKCERT_IG_PASS", "").strip() or None
IG_SESSIONFILE = _settings.get("PKCERT_IG_SESSIONFILE", "").strip() or None

# Usernames or #hashtags seeded on first run; operator adds real ones later.
SEED_TARGETS = []
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
    pool_name="instagram_pool", pool_size=5, **MYSQL_CONFIG
)


def get_db_connection():
    return db_pool.get_connection()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ig_leaks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            post_id VARCHAR(191) UNIQUE,
            author_id VARCHAR(191),
            author_username VARCHAR(255),
            detected_domains JSON,
            detected_entities JSON,
            severity VARCHAR(32) DEFAULT 'High',
            text TEXT,
            tweet_date VARCHAR(64),
            processed_at VARCHAR(64)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ig_channels (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            added_at VARCHAR(64) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    now_iso = datetime.now(timezone.utc).isoformat()
    for target in SEED_TARGETS:
        cursor.execute(
            "INSERT IGNORE INTO ig_channels (username, added_at)"
            " VALUES (%s, %s)",
            (target.strip().lower(), now_iso),
        )
    conn.commit()
    cursor.close()
    conn.close()


init_db()


# =========================================================================
# CLASSIFICATION & STORAGE
# =========================================================================
def save_matched_leak(data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT IGNORE INTO ig_leaks (
                post_id, author_id, author_username, detected_domains,
                detected_entities, severity, text, tweet_date, processed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["post_id"],
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
        print(f"[Database Error] Failed to save Instagram post: {e}")


def handle_post(post_id, author_id, author_username, text, created_at):
    is_alert, domains_found, entities_found, severity = analyze_text(text)
    if not is_alert:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    post_date_str = (
        created_at.isoformat()
        if isinstance(created_at, datetime)
        else str(created_at or now_iso)
    )
    record = {
        "post_id": str(post_id),
        "author_id": str(author_id) if author_id else "unknown",
        "author_username": author_username or "unknown",
        "detected_domains": domains_found,
        "detected_entities": entities_found,
        "severity": severity,
        "text": text,
        "tweet_date": post_date_str,
        "processed_at": now_iso,
    }
    print(
        f"\n[!] ALERT [{severity}] INSTAGRAM EXPOSURE ->"
        f" @{record['author_username']}: {text[:100]}..."
    )
    save_matched_leak(record)


# =========================================================================
# CRAWLER (instaloader) BACKGROUND WORKER
# =========================================================================
_crawler_state = {"status": "offline", "note": "Live collection disabled; local API ready."}


def get_monitored_targets():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM ig_channels")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r["username"] for r in rows]
    except Exception as e:
        print(f"[!] Error fetching Instagram targets: {e}")
        return []


def _try_login(loader, instaloader):
    """Best-effort authenticated session; safe to skip for public profiles."""
    if not IG_USER:
        return "Anonymous (public profiles only)."
    try:
        if IG_SESSIONFILE:
            loader.load_session_from_file(IG_USER, IG_SESSIONFILE)
            return f"Session loaded for @{IG_USER}."
        loader.load_session_from_file(IG_USER)  # default session path
        return f"Session loaded for @{IG_USER}."
    except Exception:
        pass
    if IG_PASS:
        try:
            loader.login(IG_USER, IG_PASS)
            return f"Logged in as @{IG_USER}."
        except Exception as e:
            return f"Login failed ({e}); using anonymous reach."
    return "No session/password; anonymous reach."


def run_crawler_poll():
    import time

    try:
        import instaloader
    except Exception:
        _crawler_state.update(
            status="offline",
            note="instaloader not installed. Run: pip install instaloader",
        )
        print(
            "[IG] instaloader missing — API stays up, crawler idle."
            " Install with: pip install instaloader"
        )
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)

    loader = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    login_note = _try_login(loader, instaloader)
    _crawler_state.update(status="online", note=login_note)
    print(f"[IG] instaloader monitor active — {login_note}")

    while True:
        targets = get_monitored_targets()
        if not targets:
            _crawler_state["note"] = "No profiles/hashtags added yet."
        for target in targets:
            try:
                if target.startswith("#"):
                    tag = target.lstrip("#")
                    posts = instaloader.Hashtag.from_name(
                        loader.context, tag
                    ).get_posts()
                    author = f"#{tag}"
                else:
                    profile = instaloader.Profile.from_username(
                        loader.context, target.lstrip("@")
                    )
                    posts = profile.get_posts()
                    author = target.lstrip("@")

                for post in islice(posts, POSTS_PER_TARGET):
                    caption = post.caption or ""
                    if not caption:
                        continue
                    handle_post(
                        post_id=post.shortcode,
                        author_id=getattr(post, "owner_username", author),
                        author_username=getattr(post, "owner_username", author),
                        text=caption,
                        created_at=getattr(post, "date_utc", None),
                    )
            except Exception as e:
                print(f"[IG crawler] {target}: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


def crawler_status():
    return [
        {
            "username": "instagram-crawler",
            "status": _crawler_state.get("status", "offline"),
            "active": _crawler_state.get("status") == "online",
            "note": _crawler_state.get("note"),
        }
    ]


# =========================================================================
# FASTAPI APP & ENDPOINTS
# =========================================================================
_bg_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bg_thread
    _bg_thread = threading.Thread(target=run_crawler_poll, daemon=True)
    if os.getenv("ENABLE_LIVE_COLLECTION", "false").lower() == "true":
        _bg_thread.start()
    yield


app = FastAPI(lifespan=lifespan)
# Locked to the local RedTraces AI dashboard instead of "*".
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
        detected = 0
        blocks = text_data.split("\n\n")
        for idx, block in enumerate(blocks):
            block_str = block.strip()
            if not block_str:
                continue
            is_alert, _, _, _ = analyze_text(block_str)
            if is_alert:
                handle_post(
                    post_id=f"file_{int(datetime.now().timestamp())}_{idx}",
                    author_id="uploaded_file",
                    author_username=filename,
                    text=block_str,
                    created_at=datetime.now(timezone.utc),
                )
                detected += 1
        return {
            "status": "success",
            "file": filename,
            "blocks_processed": len(blocks),
            "leaks_detected": detected,
        }
    except Exception as e:
        raise HTTPException(500, f"File processing error: {e}")


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
        cursor.execute(
            "INSERT IGNORE INTO ig_channels (username, added_at)"
            " VALUES (%s, %s)",
            (username, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "channel": username}
    except Exception as e:
        raise HTTPException(500, f"Database failure: {e}")


@app.get("/accounts")
async def list_accounts():
    return crawler_status()


@app.get("/channels")
async def list_channels():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, added_at FROM ig_channels ORDER BY id"
            " DESC"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
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
            "DELETE FROM ig_channels WHERE username = %s", (user_clean,)
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
            "SELECT * FROM ig_leaks ORDER BY id DESC LIMIT %s", (limit,)
        )
        rows = [clean_row_json(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Database query failed: {e}")


@app.get("/search-leaks")
async def search_leaks(
    keyword: str = Query("", description="Keyword to filter Instagram leaks"),
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if not keyword.strip():
            cursor.execute("SELECT * FROM ig_leaks ORDER BY id DESC LIMIT 500")
        else:
            p = f"%{keyword.strip()}%"
            cursor.execute(
                """
                SELECT * FROM ig_leaks
                WHERE text LIKE %s OR author_username LIKE %s
                   OR detected_entities LIKE %s OR detected_domains LIKE %s
                   OR severity LIKE %s
                ORDER BY id DESC
                """,
                (p, p, p, p, p),
            )
        rows = [clean_row_json(r) for r in cursor.fetchall()]
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
        cursor.execute("SELECT * FROM ig_leaks ORDER BY id DESC")
        rows = [clean_row_json(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()

        now = datetime.now(timezone.utc)
        today, week = [], []
        for row in rows:
            try:
                date_val = row.get("tweet_date") or row.get("processed_at")
                dt = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
                days = (now - dt).days
                if days == 0:
                    today.append(row)
                if days <= 7:
                    week.append(row)
            except Exception:
                week.append(row)
        return {"today": today, "this_week": week, "all_time": rows}
    except Exception as e:
        raise HTTPException(500, f"Date grouping failed: {e}")


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    return dashboard_html(PLATFORM, "◈", accent="#ff5da2")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8104, reload=False)


