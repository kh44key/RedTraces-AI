"""Facebook threat-intelligence collector for RedTraces AI.

Built on the same pattern as the X / Twitter collector: a FastAPI service that
polls monitored sources on a background thread, runs every post through the
shared Pakistan cyber-threat classifier, and stores matches in MySQL. The unified
:3000 dashboard consumes the identical REST shape (/leaks, /channels, /accounts,
/search-leaks, ...), so Facebook plugs in exactly like X and Telegram.

Crawler backend: `facebook-scraper` (public pages / groups). Optional cookies for
authenticated reach are read from .pkcert.env (PKCERT_FB_COOKIES = path to a
Netscape cookies.txt). If the library or a reachable session is missing, the API
still serves cleanly and file uploads still classify — it just reports the
crawler as offline, mirroring how X degrades when no accounts are active.
"""

import json
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

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
POSTS_PER_TARGET = 15
PLATFORM = "FACEBOOK"

# Reuses the now-unused telegram_leaks_db (pkcert already has full grants on it)
# with Facebook-specific tables, so no MySQL-root DB creation is needed.
MYSQL_CONFIG = mysql_config("facebook_leaks_db")

_settings = load_private_settings()
# Optional Netscape cookies.txt exported from a logged-in browser session.
FB_COOKIES = _settings.get("PKCERT_FB_COOKIES", "").strip() or None

# Pages/groups seeded on first run. The operator adds the real monitored
# sources from the dashboard; these are just illustrative and can be removed.
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
    pool_name="facebook_pool", pool_size=5, **MYSQL_CONFIG
)


def get_db_connection():
    return db_pool.get_connection()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fb_leaks (
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
        CREATE TABLE IF NOT EXISTS fb_channels (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            added_at VARCHAR(64) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    now_iso = datetime.now(timezone.utc).isoformat()
    for target in SEED_TARGETS:
        cursor.execute(
            "INSERT IGNORE INTO fb_channels (username, added_at)"
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
            INSERT IGNORE INTO fb_leaks (
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
        print(f"[Database Error] Failed to save Facebook post: {e}")


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
        f"\n[!] ALERT [{severity}] FACEBOOK EXPOSURE ->"
        f" {record['author_username']}: {text[:100]}..."
    )
    save_matched_leak(record)


# =========================================================================
# CRAWLER (facebook-scraper) BACKGROUND WORKER
# =========================================================================
_crawler_state = {"status": "offline", "note": "Live collection disabled; local API ready."}


def get_monitored_targets():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM fb_channels")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r["username"] for r in rows]
    except Exception as e:
        print(f"[!] Error fetching Facebook targets: {e}")
        return []


def run_crawler_poll():
    import time

    try:
        from facebook_scraper import get_posts
    except Exception:
        _crawler_state.update(
            status="offline",
            note="facebook-scraper not installed. Run: pip install facebook-scraper",
        )
        print(
            "[FB] facebook-scraper missing — API stays up, crawler idle."
            " Install with: pip install facebook-scraper"
        )
        while True:  # keep the service alive; file uploads still classify
            time.sleep(POLL_INTERVAL_SECONDS)

    _crawler_state.update(
        status="online",
        note="Cookies loaded." if FB_COOKIES else "Public reach (no cookies).",
    )
    print("[FB] facebook-scraper monitor active...")

    while True:
        targets = get_monitored_targets()
        if not targets:
            _crawler_state["note"] = "No pages/groups added yet."
        for target in targets:
            try:
                for post in get_posts(
                    target,
                    pages=2,
                    cookies=FB_COOKIES,
                    options={"comments": False, "reactors": False},
                ):
                    text = post.get("text") or ""
                    if not text:
                        continue
                    handle_post(
                        post_id=post.get("post_id")
                        or f"{target}_{post.get('time')}",
                        author_id=target,
                        author_username=target,
                        text=text,
                        created_at=post.get("time"),
                    )
            except Exception as e:
                print(f"[FB crawler] @{target}: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


def crawler_status():
    """Shaped like the X pool's /accounts so the dashboard renders it the same."""
    return [
        {
            "username": "facebook-crawler",
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
# Locked to the local RedTraces AI dashboard instead of "*" so no arbitrary website
# can reach this loopback API from the operator's browser.
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
            "INSERT IGNORE INTO fb_channels (username, added_at)"
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
            "SELECT id, username, added_at FROM fb_channels ORDER BY id"
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
            "DELETE FROM fb_channels WHERE username = %s", (user_clean,)
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
            "SELECT * FROM fb_leaks ORDER BY id DESC LIMIT %s", (limit,)
        )
        rows = [clean_row_json(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Database query failed: {e}")


@app.get("/search-leaks")
async def search_leaks(
    keyword: str = Query("", description="Keyword to filter Facebook leaks"),
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if not keyword.strip():
            cursor.execute("SELECT * FROM fb_leaks ORDER BY id DESC LIMIT 500")
        else:
            p = f"%{keyword.strip()}%"
            cursor.execute(
                """
                SELECT * FROM fb_leaks
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
        cursor.execute("SELECT * FROM fb_leaks ORDER BY id DESC")
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
    return dashboard_html(PLATFORM, "f", accent="#4f93e6")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8103, reload=False)


