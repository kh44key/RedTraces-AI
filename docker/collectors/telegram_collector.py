import asyncio
import json
import os
import re
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone

import mysql.connector
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from mysql.connector import pooling
from pydantic import BaseModel
from pkcert_config import mysql_config, get_secret
from telethon import TelegramClient, connection, events
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    InviteHashExpiredError,
    UserAlreadyParticipantError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

# =========================================================================
# CONFIGURATION
# =========================================================================
API_ID = int(get_secret("TELEGRAM_API_ID", "0") or "0")
API_HASH = get_secret("TELEGRAM_API_HASH")


# MySQL Database Configuration
MYSQL_CONFIG = mysql_config("telegram_leaks_db")

# Dynamic list of watched channel handles/IDs loaded from MySQL
CHANNELS_TO_WATCH = []
# =========================================================================


# Ensure Database exists on launch
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
        print(f"[!] MySQL Setup Notice: {e}")


create_database_if_not_exists()

# Initialize MySQL Pool
db_pool = pooling.MySQLConnectionPool(
    pool_name="telegram_pool", pool_size=5, **MYSQL_CONFIG
)


def get_db_connection():
    return db_pool.get_connection()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Leaks Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            channel VARCHAR(255),
            message_id BIGINT,
            detected_domains JSON,
            detected_entities JSON,
            text TEXT,
            message_date VARCHAR(64),
            processed_at VARCHAR(64),
            UNIQUE KEY unique_msg (channel, message_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # Managed Channels Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watched_channels (
            id INT AUTO_INCREMENT PRIMARY KEY,
            channel_id VARCHAR(64) UNIQUE,
            title VARCHAR(255),
            handle VARCHAR(255),
            added_at VARCHAR(64)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    conn.commit()

    # Load previously saved channels into memory
    cursor.execute("SELECT handle FROM watched_channels")
    rows = cursor.fetchall()
    global CHANNELS_TO_WATCH
    CHANNELS_TO_WATCH = [
        row[0] for row in rows if row[0] and row[0] != "unknown"
    ]

    cursor.close()
    conn.close()


init_db()

# Telegram Client Setup
client = None
collector_state = {"status": "offline", "note": "Live collection disabled; local API ready."}

# =========================================================================
# INDICATORS
# =========================================================================
PAKISTAN_ENTITY_INDICATORS = list(
    set([
        "pakistan", "pakistani", "pak", "pk", "gov.pk", "gop.pk",
        "pakistan government", "prime minister", "president of pakistan",
        "cabinet division", "punjab government", "sindh government",
        "kpk government", "balochistan government", "nadra", "fia", "pta",
        "fbr", "hec", "secp", "state bank of pakistan", "sbp", "nepra",
        "pemra", "ogra", "pakistan customs", "passport office",
        "excise and taxation", "pakistan post", "pakistan railways",
        "rescue 1122", "cda", "wapda", "ndma", "pdma", "nab", "peca",
        "ppra", "benazir income support", "bisp", "ehsaas program", "pmdc",
        "pcp", "psx", "sbp pakistan", "hec pakistan", "punjab", "sindh",
        "khyber pakhtunkhwa", "kp", "kpk", "balochistan", "gilgit baltistan",
        "gb", "azad kashmir", "ajk", "islamabad capital territory", "ict",
        "islamabad", "rawalpindi", "lahore", "karachi", "peshawar", "quetta",
        "faisalabad", "multan", "sialkot", "gujranwala", "hyderabad",
        "hyderabad sindh", "sukkur", "bahawalpur", "abbottabad", "mansehra",
        "mardan", "kohat", "hangu", "swat", "mingora", "charsadda", "nowshera",
        "dera ismail khan", "d i khan", "bannu", "tank", "lakki marwat",
        "haripur", "attock", "jhelum", "gujrat", "sargodha", "sheikhupura",
        "kasur", "okara", "rahim yar khan", "vehari", "sahiwal", "narowal",
        "hafizabad", "khanewal", "toba tek singh", "muzaffargarh",
        "dera ghazi khan", "rajanpur", "larkana", "nawabshah", "mirpur khas",
        "jacobabad", "khairpur", "gwadar", "turbat", "khuzdar", "chaman",
        "zhob", "gilgit", "skardu", "hunza", "muzaffarabad", "mirpur", "kotli",
        "iesco", "lesco", "pesco", "gepco", "mepco", "hesco", "qesco", "tesco",
        "fesco", "ptcl", "jazz", "zong", "ufone", "telenor pakistan", "onetel",
        "nayatel", "stormfiber", "hbl", "habib bank", "ubl", "united bank",
        "mcb", "allied bank", "abl", "meezan bank", "bank alfalah",
        "bank al habib", "faysal bank", "askari bank", "bankislami",
        "soneri bank", "silkbank", "summit bank", "js bank", "nbp",
        "national bank of pakistan", "easypaisa", "jazzcash", "raast", "cnic",
        "nicop", "poc", "passport", "b-form", "smart cnic",
        "computerized national identity card", "pak army", "pakistan army",
        "pakistan navy", "pakistan air force", "isi", "isi pakistan",
        "pak rangers", "frontier corps", "fc", "ssg", "asf", "punjab police",
        "sindh police", "kp police", "islamabad police", "pia", "pso", "nust",
        "comsats", "fast nuces", "uet", "uet peshawar", "iiui", "numl",
        "giki", "pieas", "air university", "bahria university", "uet lahore",
        "uop", "qau", "pucit", "پاکستان", "پاک", "اسلام آباد", "راولپنڈی",
        "لاہور", "کراچی", "پشاور", "کوئٹہ", "نادرا", "ایف آئی اے", "پی ٹی اے",
        "ایف بی آر", "پاک فوج", "پاکستان آرمی", "پاکستان نیوی",
        "پاکستان ائیر فورس", "شناختی کارڈ", "پاسپورٹ", "حکومت پاکستان"
    ])
)

CONTEXT_INDICATORS = list(
    set([
        "leak", "selling", "sale", "database", "db", "combo", "breach", "dump",
        "leads", "stealer", "logs", "price", "combolist", "hack", "backdoor",
        "browser update", "fake captcha", "powershell", "data", "file", "files",
        "record", "records", "csv", "sql", "json", "txt", "information",
        "hacked by", "defaced by", "owned by", "pwned by", "rooted by",
        "touched by", "hijacked by", "gr33tz", "greetz", "shout out to",
        "we are anonymous", "we are legion", "expect us", "r00ted", "matrixman",
        "clan_", "lulzghost", "ironheart", "lulzsec", "anonghost", "chinafans",
        "manusia biasa", "anonsec", "vernest team", "indian cyber army",
        "gujarat cyber army", "kerala cyber army", "haryana cyber army",
        "indian cyber mafia", "indian cyber force", "indian cyber gang",
        "indian cyber warriors", "pak cyber army", "pakistan cyber army",
        "pak cyber force", "team insane pak", "pak hackers", "pakistani hackers",
        "pak haxors", "pakistani haxors", "pak leets", "pakistan ghost",
        "pak ghost", "muslim cyber army", "islamic cyber army", "pak cyber squad",
        "pak cyber warriors", "pakistan cyber warriors", "pak cyber mafia",
        "haxors pakistan", "team pak", "pakistan team", "cyber army of pakistan",
        "pakistani cyber team", "anti-pakistan", "anti pakistan",
        "down with pakistan", "free kashmir from pakistan",
        "free balochistan from pakistan", "kill pak", "pakistan army is corrupt",
        "pakistan isi is corrupt", "pakistan government is corrupt",
        "pakistan army is terrorist", "pakistan isi is terrorist",
        "pakistan government is terrorist", "pakistan army is criminal",
        "pakistan isi is criminal", "pakistan government is criminal",
        "ہیک کر دیا", "ہیکرز", "دھمکی", "تحریک", "آزادی کشمیر", "آزادی بلوچستان",
        "پاکستان ہیک", "پاکستانی ہیکرز", "سرکاری ہیک", "حکومت ہیک", "کشمیر بچاؤ",
        "بلوچستان آزاد", "پاکستان ختم", "پاکستان ٹوٹ جائے", "پاک فوج ختم",
        "کشمیر آزاد", "پاکستان دشمن", "پاکستان کا خاتمہ", "پاکستان ناکام",
        "پاکستان ہار گیا", "b374k", "wso webshell", "c99shell", "coinhive.min.js",
        "crypto-loot.com", "eval(atob(", "eval(unescape(",
        "eval(function(p, a, c, k", "string.fromcharcode(",
        "window.location.replace(", "your site has been hacked",
        "your site has been defaced", "your site has been compromised",
        "your site has been pwned", "index.txt", "de-face.txt", "hacked.txt",
        "freepalestine.html", "0x.txt", "pwned.txt", "hacked.php"
    ])
)


def analyze_text(text):
    if not text:
        return False, [], []

    text_lower = text.lower()
    domain_pattern = r"\b[a-zA-Z0-9.-]+\.(?:gov|pk|gov\.pk)\b"
    matched_domains = re.findall(domain_pattern, text_lower)
    matched_entities = [
        e for e in PAKISTAN_ENTITY_INDICATORS if e in text_lower
    ]
    has_indicator = any(
        indicator in text_lower for indicator in CONTEXT_INDICATORS
    )

    if (matched_domains or matched_entities) and has_indicator:
        return True, list(set(matched_domains)), list(set(matched_entities))

    return False, [], []


def save_matched_leak(data):
    """Saves matched leaks directly into MySQL database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT IGNORE INTO leaks (
                channel, message_id, detected_domains, 
                detected_entities, text, message_date, processed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["channel"],
                data["message_id"],
                json.dumps(data["detected_domains"]),
                json.dumps(data["detected_entities"]),
                data["text"],
                str(data["message_date"]),
                str(data["processed_at"]),
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Database Error] Failed saving Telegram leak: {e}")


def clean_row_json(row):
    """Parses JSON stored fields into standard Python lists."""
    for field in ["detected_domains", "detected_entities"]:
        if isinstance(row.get(field), str):
            try:
                row[field] = json.loads(row[field])
            except Exception:
                row[field] = []
        elif row.get(field) is None:
            row[field] = []
    row.setdefault("severity", "unknown")
    return row


# =========================================================================
# FASTAPI APP & TELETHON MESSAGING EVENT
# =========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    task = None
    enabled = get_secret("TELEGRAM_ENABLED", "false").lower() == "true"
    try:
        if enabled and API_ID and API_HASH:
            client = TelegramClient("/data/monitor_session", API_ID, API_HASH, use_ipv6=False)
            await asyncio.wait_for(client.connect(), timeout=25)
            if await client.is_user_authorized():
                client.add_event_handler(incoming_message_handler, events.NewMessage())
                collector_state.update(status="online", note="Authenticated session; monitoring configured channels.")
                task = asyncio.create_task(client.run_until_disconnected())
            else:
                collector_state.update(status="offline", note="Session login required; see the setup guide.")
                await client.disconnect()
        elif enabled:
            collector_state.update(status="offline", note="Set TELEGRAM_API_ID and TELEGRAM_API_HASH.")
    except Exception:
        collector_state.update(status="offline", note="Telegram connection failed; local API remains available.")
        if client and client.is_connected():
            await client.disconnect()
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if client and client.is_connected():
            await client.disconnect()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def incoming_message_handler(event):
    # Only inspect channels explicitly configured by the operator.
    chat = await event.get_chat()
    handle = str(getattr(chat, "username", "") or "").lower()
    channel_id = str(getattr(chat, "id", ""))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT channel_id, handle FROM watched_channels")
        watched = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    if not any(str(row["channel_id"]) == channel_id or
               (handle and str(row["handle"]).lower() == handle) for row in watched):
        return
    # Classify matching channel updates
    raw_text = event.raw_text
    is_alert, domains_found, entities_found = analyze_text(raw_text)

    if is_alert:
        channel_name = "unknown"
        if (
            event.chat
            and hasattr(event.chat, "username")
            and event.chat.username
        ):
            channel_name = event.chat.username
        elif event.chat and hasattr(event.chat, "title"):
            channel_name = event.chat.title

        record = {
            "channel": channel_name,
            "message_id": event.message.id,
            "detected_domains": domains_found,
            "detected_entities": entities_found,
            "text": raw_text,
            "message_date": event.message.date,
            "processed_at": datetime.now(timezone.utc),
        }

        snippet = raw_text[:140].replace("\n", " ")
        print(f"\n[!] ALERT: TELEGRAM LEAK IDENTIFIED")
        print(f"Source Channel : @{record['channel']}")
        print(
            "Matched Domain :"
            f" {', '.join(domains_found) if domains_found else '(none)'}"
        )
        print(
            "Matched Entity :"
            f" {', '.join(entities_found) if entities_found else '(none)'}"
        )
        print(f"Snippet        : {snippet}...")
        print("=" * 60)

        save_matched_leak(record)


# =========================================================================
# ENDPOINTS
# =========================================================================
class AddChannelRequest(BaseModel):
    link: str


def parse_link(link: str):
    link = link.strip()
    
    # Private invite links (e.g. https://t.me/joinchat/... or https://t.me/+...)
    invite_match = re.search(r"(?:joinchat/|\+)([A-Za-z0-9_-]+)", link)
    if invite_match:
        return invite_match.group(1), True

    # Public t.me links (e.g. https://t.me/jundalnabi)
    public_match = re.search(r"t\.me/([A-Za-z0-9_]+)", link)
    if public_match:
        return public_match.group(1), False

    # Raw usernames or handles
    clean_handle = link.lstrip("@")
    return clean_handle, False


@app.post("/add-channel")
async def add_channel(req: AddChannelRequest):
    identifier, is_private = parse_link(req.link)
    if not identifier or (not is_private and not re.fullmatch(r"[A-Za-z0-9_]{5,32}", identifier)):
        raise HTTPException(422, "Use a valid Telegram channel username or invite link.")
    if collector_state["status"] != "online":
        if is_private:
            raise HTTPException(409, "Private invite links require an authenticated Telegram session.")
        handle = identifier.lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO watched_channels (channel_id,title,handle,added_at) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE handle=VALUES(handle)",
                           ("pending:" + handle, handle, handle, datetime.now(timezone.utc).isoformat()))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        if handle not in CHANNELS_TO_WATCH:
            CHANNELS_TO_WATCH.append(handle)
        return {"status": "saved", "handle": handle, "note": "Saved locally; connect Telegram and add again to join."}

    try:
        if is_private:
            try:
                updates = await client(ImportChatInviteRequest(identifier))
                entity = updates.chats[0]
            except UserAlreadyParticipantError:
                entity = await client.get_entity(req.link)
        else:
            # Ensure handle is properly formatted with @ for Telethon lookups
            target_handle = f"@{identifier}" if not identifier.startswith("@") else identifier
            
            # Retrieve Telegram entity
            entity = await client.get_entity(target_handle)
            
            # Join channel if not already joined
            await client(JoinChannelRequest(entity))

        channel_id = str(entity.id)
        title = getattr(entity, "title", identifier)
        handle = getattr(entity, "username", identifier) or identifier

        # Resolve any locally configured pending entry before storing its real ID.
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watched_channels WHERE channel_id = %s", ("pending:" + handle.lower(),))
        cursor.execute(
            """
            INSERT IGNORE INTO watched_channels (channel_id, title, handle, added_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                channel_id,
                title,
                handle,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        if handle not in CHANNELS_TO_WATCH:
            CHANNELS_TO_WATCH.append(handle)

    except UsernameNotOccupiedError:
        raise HTTPException(
            status_code=404,
            detail=f"The handle '@{identifier}' does not exist on Telegram."
        )
    except (ChannelPrivateError, ChannelInvalidError):
        raise HTTPException(
            status_code=400,
            detail=f"Channel '@{identifier}' is private, restricted, or banned by Telegram."
        )
    except InviteHashExpiredError:
        raise HTTPException(
            status_code=400,
            detail="This invite link has expired."
        )
    except FloodWaitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited by Telegram. Retry in {e.seconds}s."
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve '@{identifier}'. Channel may be deleted, private, or geo-blocked."
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not join channel: {str(e)}"
        )

    return {
        "status": "ok",
        "channel_id": channel_id,
        "title": title,
        "handle": handle,
    }


@app.get("/accounts")
async def accounts():
    return [{"username": "telegram-session", "status": collector_state["status"],
             "active": collector_state["status"] == "online", "note": collector_state["note"]}]


@app.delete("/remove-channel")
async def remove_channel(username: str):
    identifier, _ = parse_link(username)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM watched_channels WHERE LOWER(handle) = %s", (identifier.lower(),))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    CHANNELS_TO_WATCH[:] = [h for h in CHANNELS_TO_WATCH if h.lower() != identifier.lower()]
    return {"status": "removed"}


@app.get("/channels")
async def get_channels():
    """Returns the list of monitored channels."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM watched_channels ORDER BY id DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Failed retrieving channel list: {e}")


@app.get("/leaks")
async def list_leaks(limit: int = 1000):
    """Retrieve leaks stored in MySQL."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM leaks ORDER BY id DESC LIMIT %s", (limit,))
        rows = cursor.fetchall()
        rows = [clean_row_json(r) for r in rows]
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Failed fetching database leaks: {e}")


@app.get("/search-leaks")
async def search_leaks(
    keyword: str = Query("", description="Keyword to filter Telegram leaks"),
):
    """Search leaks stored in MySQL by keyword."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if not keyword.strip():
            cursor.execute("SELECT * FROM leaks ORDER BY id DESC LIMIT 200")
        else:
            search_param = f"%{keyword.strip()}%"
            query_sql = """
                SELECT * FROM leaks 
                WHERE text LIKE %s 
                   OR channel LIKE %s 
                   OR detected_entities LIKE %s 
                   OR detected_domains LIKE %s 
                ORDER BY id DESC
            """
            cursor.execute(
                query_sql,
                (search_param, search_param, search_param, search_param),
            )

        rows = cursor.fetchall()
        rows = [clean_row_json(r) for r in rows]
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(500, f"Search failed: {e}")


# =========================================================================
# DASHBOARD UI
# =========================================================================
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RedTraces AI — Telegram Signal Core</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            :root { --tg-blue:#229ed9; --tg-dark:#168acd; --tg-pale:#e7f5fc; --tg-bg:#eef3f7; --tg-text:#17212b; --tg-muted:#708499; --tg-line:#dce6ed; }
            * { box-sizing:border-box; }
            body { min-height:100vh; background:linear-gradient(145deg,#e9f5fb 0,#f5f8fa 42%,#eaf1f5 100%); color:var(--tg-text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
            .container-fluid { max-width:1480px; margin:auto; background:rgba(255,255,255,.68); border:1px solid rgba(255,255,255,.85); border-radius:24px; padding:26px!important; box-shadow:0 20px 55px rgba(48,86,108,.12); backdrop-filter:blur(16px); }
            h2 { color:#142b3a; letter-spacing:-.4px; font-size:0; }
            h2::after { content:'RedTraces AI // Telegram Signal Core'; font-size:25px; }
            .border-bottom { border-color:var(--tg-line)!important; }
            .text-muted { color:var(--tg-muted)!important; }
            .card { background:#fff; border:1px solid var(--tg-line); border-radius:17px; overflow:hidden; color:var(--tg-text); box-shadow:0 7px 22px rgba(40,75,96,.06); }
            .card-header { background:#fff; border-color:var(--tg-line)!important; padding:17px 20px; color:#263b4a; }
            .nav-tabs { border:0; background:#fff; padding:7px; border-radius:15px; display:inline-flex; gap:5px; box-shadow:0 5px 18px rgba(40,75,96,.06); }
            .nav-tabs .nav-link { color:#607587; border:none!important; border-radius:10px; padding:11px 18px; font-weight:650; cursor:pointer; font-size:0; }
            #live-tab::after { content:'Detected Leaks'; font-size:14px; }
            #query-tab::after { content:'Search Database'; font-size:14px; }
            #channels-tab::after { content:'Channel Management'; font-size:14px; }
            .nav-tabs .nav-link:hover { color:var(--tg-dark); background:#f0f8fc; }
            .nav-tabs .nav-link.active { color:#fff; background:var(--tg-blue); box-shadow:0 6px 15px rgba(34,158,217,.25); }
            .table { color:var(--tg-text); --bs-table-bg:transparent; --bs-table-hover-bg:#f6fbfe; --bs-table-color:var(--tg-text); --bs-table-hover-color:var(--tg-text); }
            .table thead th { background:#f6f9fb!important; color:var(--tg-muted)!important; border-color:var(--tg-line); padding:13px 16px; font-size:11px; letter-spacing:.55px; text-transform:uppercase; white-space:nowrap; }
            .table tbody td { border-color:#edf2f5; padding:15px 16px; font-size:13px; }
            .badge-entity { background:#dff3fc; color:#147eae; border-radius:20px; padding:6px 9px; }
            .badge-domain { background:#ffe5eb; color:#c33f58; border-radius:20px; padding:6px 9px; }
            .badge.bg-success { background:#dff8ea!important; color:#21945b; border-radius:20px; }
            .badge.bg-secondary { background:#edf2f5!important; color:#667b8c; }
            .text-info { color:var(--tg-dark)!important; }
            .table .text-white { color:var(--tg-dark)!important; font-weight:600; }
            code { color:var(--tg-dark); background:var(--tg-pale); padding:4px 7px; border-radius:6px; }
            .msg-box { max-width:500px; word-wrap:break-word; white-space:pre-wrap; line-height:1.55; }
            .form-control.bg-dark { min-height:48px; border-radius:11px; background:#f7fafc!important; color:var(--tg-text)!important; border-color:#d8e3ea!important; box-shadow:none; }
            .form-control:focus { border-color:var(--tg-blue)!important; background:#fff!important; }
            .btn { border-radius:10px; font-weight:650; }
            .btn-primary,.btn-success { min-height:48px; background:var(--tg-blue); border-color:var(--tg-blue); }
            .btn-primary:hover,.btn-success:hover { background:var(--tg-dark); border-color:var(--tg-dark); }
            .btn-outline-info { color:var(--tg-dark); border-color:#a9dced; background:#edf8fd; }
            .btn-outline-info:hover { background:var(--tg-blue); border-color:var(--tg-blue); color:#fff; }
            #query-panel .card:first-child .card-header,
            #channels-panel .col-md-5 .card-header,
            #channels-panel .col-md-7 .card-header { font-size:0; }
            #query-panel .card:first-child .card-header::after { content:'Search Stored Messages'; font-size:16px; }
            #channels-panel .col-md-5 .card-header::after { content:'Add New Telegram Channel'; font-size:16px; }
            #channels-panel .col-md-7 .card-header::after { content:'Monitored Channels Registry'; font-size:16px; }
            @media (max-width:767px) { body { padding:10px!important; } .container-fluid { padding:16px!important; border-radius:17px; } .nav-tabs { display:flex; width:100%; overflow:auto; flex-wrap:nowrap; } .nav-tabs .nav-link { white-space:nowrap; padding:10px 13px; } h2 { font-size:20px; } .card { border-radius:13px; } }
            
            /* CINEMATIC SECURITY HUD STYLING */
            :root{--void:#02040d;--panel:rgba(7,14,31,.82);--cyan:#00eaff;--blue:#177dff;--violet:#8a5cff;--pink:#ff2bd6;--acid:#b8ff35;--ink:#dffaff}
            html{background:var(--void)}body{background:radial-gradient(circle at 55% -15%,#173275 0,#070b1c 40%,#02040d 82%);color:var(--ink);overflow-x:hidden}
            body::before{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;background:repeating-linear-gradient(0deg,transparent 0 3px,rgba(0,234,255,.025) 4px),linear-gradient(90deg,rgba(0,234,255,.03) 1px,transparent 1px),linear-gradient(rgba(0,234,255,.025) 1px,transparent 1px);background-size:100% 4px,70px 70px,70px 70px}
            #cyberCanvas{position:fixed;inset:0;width:100%;height:100%;z-index:-2}.energy-bolt{position:fixed;top:-20%;left:52%;width:2px;height:140%;z-index:-1;opacity:.35;background:linear-gradient(transparent,var(--cyan),#fff,var(--violet),transparent);filter:drop-shadow(0 0 14px var(--cyan));transform:rotate(17deg);animation:bolt 4.8s infinite steps(1)}
            @keyframes bolt{0%,88%,100%{opacity:.04}89%{opacity:.9;transform:rotate(17deg) translateX(-9px)}91%{opacity:.16}93%{opacity:.7;transform:rotate(17deg) translateX(12px)}}
            .container-fluid{max-width:1600px;position:relative;background:linear-gradient(145deg,rgba(4,10,25,.9),rgba(10,18,41,.74));border:1px solid rgba(0,234,255,.25);box-shadow:0 30px 90px #000,0 0 70px rgba(0,126,255,.12) inset;backdrop-filter:blur(18px);transform-style:preserve-3d}
            h2{font-size:0!important}h2::after{content:'REDTRACES AI // TELEGRAM CORE';color:#fff;font-size:25px;letter-spacing:1.5px;text-shadow:0 0 16px var(--cyan),0 0 34px var(--blue)}.text-muted{color:#7f9eb5!important}.border-bottom{border-color:rgba(0,234,255,.22)!important}
            .engine-deck{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 16px;margin:-4px 0 18px;border:1px solid rgba(0,234,255,.2);border-radius:13px;background:rgba(3,9,23,.72);box-shadow:0 12px 30px rgba(0,0,0,.32)}.hud-kicker{color:var(--cyan);font:700 10px Consolas,monospace;letter-spacing:3px}.engine-controls{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.engine-btn{border:1px solid;border-radius:8px;padding:8px 12px;color:#fff;background:#050c1d;font:700 10px Consolas,monospace;letter-spacing:1px;transition:.25s}.engine-btn:hover{transform:translateY(-2px)}.engine-start{border-color:var(--acid)}.engine-start:hover{background:var(--acid);color:#071005;box-shadow:0 0 25px rgba(184,255,53,.5)}.engine-stop{border-color:#ff335f}.engine-stop:hover{background:#ff335f;box-shadow:0 0 25px rgba(255,51,95,.5)}.engine-state{display:flex;align-items:center;gap:7px;color:var(--cyan);font:700 10px Consolas,monospace}.engine-state i{width:7px;height:7px;border-radius:50%;background:var(--acid);box-shadow:0 0 12px var(--acid);animation:pulse 1.3s infinite}@keyframes pulse{50%{opacity:.3;transform:scale(.65)}}
            .stats-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin-bottom:20px}.stat{position:relative;overflow:hidden;min-height:92px;padding:16px 18px;border:1px solid rgba(0,234,255,.18);border-radius:14px;background:linear-gradient(145deg,rgba(8,19,42,.9),rgba(4,8,21,.78));box-shadow:0 12px 30px rgba(0,0,0,.3);transition:.3s}.stat:hover{transform:perspective(700px) rotateX(5deg) translateY(-5px);border-color:var(--cyan);box-shadow:0 18px 42px #000,0 0 25px rgba(0,234,255,.15)}.stat::after{content:'';position:absolute;right:-25px;bottom:-42px;width:105px;height:105px;border:1px solid currentColor;border-radius:50%;opacity:.2;box-shadow:0 0 25px currentColor}.stat:nth-child(1){color:var(--cyan)}.stat:nth-child(2){color:var(--violet)}.stat:nth-child(3){color:var(--pink)}.stat:nth-child(4){color:var(--acid)}.stat-label{display:block;opacity:.72;font:700 9px Consolas,monospace;letter-spacing:2px}.stat-value{display:block;margin-top:9px;color:#fff;font:800 27px Consolas,monospace;text-shadow:0 0 15px currentColor}
            .nav-tabs{border:1px solid rgba(0,234,255,.2);background:rgba(4,10,24,.76);box-shadow:0 10px 30px rgba(0,0,0,.35)}.nav-tabs .nav-link{color:#7898b1}.nav-tabs .nav-link:hover{color:var(--cyan);background:rgba(0,234,255,.07)}.nav-tabs .nav-link.active{color:#031018;background:linear-gradient(110deg,var(--cyan),#6cf3ff);box-shadow:0 0 25px rgba(0,234,255,.5)}
            .card{background:linear-gradient(150deg,rgba(8,18,39,.94),rgba(3,8,20,.88));border:1px solid rgba(0,234,255,.2);color:var(--ink);box-shadow:0 18px 45px rgba(0,0,0,.4),0 0 30px rgba(23,125,255,.07) inset;transition:.28s}.card:hover{transform:perspective(1100px) translateY(-3px);border-color:rgba(0,234,255,.48);box-shadow:0 24px 55px rgba(0,0,0,.5),0 0 35px rgba(0,234,255,.1)}.card-header{color:#dffaff;background:linear-gradient(90deg,rgba(0,234,255,.09),transparent);border-color:rgba(0,234,255,.18)!important}.card-header::before{content:'◈';color:var(--cyan);margin-right:9px;text-shadow:0 0 12px var(--cyan)}.card-body{background:transparent}
            .table{--bs-table-bg:transparent;--bs-table-color:#bad3e4;--bs-table-hover-bg:rgba(0,234,255,.055);--bs-table-hover-color:#fff;color:#bad3e4}.table thead th{background:rgba(0,234,255,.055)!important;color:var(--cyan)!important;border-color:rgba(0,234,255,.13);font-family:Consolas,monospace}.table tbody td{border-color:rgba(84,145,184,.12)}.table .text-white{color:#9bd9ff!important}.text-info{color:var(--cyan)!important;text-shadow:0 0 9px rgba(0,234,255,.35)}.badge-entity{color:#07101a;background:linear-gradient(110deg,var(--cyan),#7ff7ff)}.badge-domain{color:#fff;background:linear-gradient(110deg,#ff335f,var(--pink))}.badge.bg-success{color:var(--acid)!important;background:rgba(184,255,53,.08)!important;border:1px solid rgba(184,255,53,.35)}.badge.bg-secondary{color:#c7e9ff;background:rgba(23,125,255,.2)!important}code{color:#d8cfff;background:rgba(138,92,255,.15);border:1px solid rgba(138,92,255,.25)}
            .form-control.bg-dark{color:#e8fbff!important;background:rgba(1,7,18,.8)!important;border-color:rgba(0,234,255,.23)!important}.form-control:focus{color:#fff!important;background:#050c1c!important;border-color:var(--cyan)!important;box-shadow:0 0 24px rgba(0,234,255,.13)!important}.form-control::placeholder{color:#58758b}.btn-primary,.btn-success{border:0;color:#041018;background:linear-gradient(110deg,var(--cyan),#45a8ff);box-shadow:0 0 20px rgba(0,234,255,.2)}.btn-primary:hover,.btn-success:hover{color:#fff;background:linear-gradient(110deg,var(--violet),var(--pink));box-shadow:0 0 28px rgba(255,43,214,.35);transform:translateY(-2px)}.btn-outline-info{color:var(--cyan);border-color:rgba(0,234,255,.45);background:rgba(0,234,255,.06)}
            .system-log{position:fixed;right:16px;bottom:14px;z-index:50;width:min(350px,calc(100vw - 32px));padding:10px 13px;border:1px solid rgba(0,234,255,.25);border-radius:9px;background:rgba(2,7,18,.9);color:#7fefff;font:10px Consolas,monospace;box-shadow:0 10px 35px #000;pointer-events:none}.engine-off #cyberCanvas,.engine-off .energy-bolt{opacity:0}.engine-off .engine-state{color:#ff607e}.engine-off .engine-state i{background:#ff335f;box-shadow:0 0 10px #ff335f;animation:none}
            @media(max-width:900px){.stats-grid{grid-template-columns:repeat(2,1fr)}.engine-deck{align-items:flex-start;flex-direction:column}}@media(max-width:520px){body{padding:6px!important}.stats-grid{gap:8px}.stat{min-height:78px;padding:12px}.stat-value{font-size:20px}.system-log{display:none}}
        </style>
    </head>
    <body class="p-4">
        <canvas id="cyberCanvas" aria-hidden="true"></canvas>
        <div class="energy-bolt" aria-hidden="true"></div>
        <div class="container-fluid">
            <!-- HEADER -->
            <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                <div>
                    <h2 class="fw-bold mb-0">✈️ RedTraces AI Telegram Signal Core</h2>
                    <small class="text-muted">Channel-native monitoring surface with RedTraces AI enrichment and IOC analysis</small>
                </div>
                <div>
                    <span class="badge bg-success p-2">Telegram MTProxy Active</span>
                    <button onclick="refreshData()" class="btn btn-sm btn-outline-info ms-2">🔄 Refresh Data</button>
                </div>
            </div>

            <div class="engine-deck">
                <div><div class="hud-kicker">SECURE INTELLIGENCE NODE // LIVE TELEMETRY</div><small class="text-muted">Animated threat-processing core and continuous data scan</small></div>
                <div class="engine-controls"><span class="engine-state" id="engineState"><i></i><b>ENGINE ONLINE</b></span><button onclick="startEngine()" class="engine-btn engine-start">START ENGINE</button><button onclick="stopEngine()" class="engine-btn engine-stop">STOP ENGINE</button></div>
            </div>
            <div class="stats-grid">
                <div class="stat"><span class="stat-label">EXTRACTED RECORDS</span><span class="stat-value" id="statLeaks">000</span></div>
                <div class="stat"><span class="stat-label">MONITORED CHANNELS</span><span class="stat-value" id="statChannels">00</span></div>
                <div class="stat"><span class="stat-label">CORE INTEGRITY</span><span class="stat-value">99.8%</span></div>
                <div class="stat"><span class="stat-label">SCAN FREQUENCY</span><span class="stat-value" id="scanRate">24/s</span></div>
            </div>

            <!-- NAVIGATION TABS -->
            <ul class="nav nav-tabs mb-4" id="dashboardTabs" role="tablist">
                <li class="nav-item">
                    <button class="nav-link active" id="live-tab" data-bs-toggle="tab" data-bs-target="#live-panel" type="button" onclick="loadLeaks()">🚨 Detected Leaks</button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" id="query-tab" data-bs-toggle="tab" data-bs-target="#query-panel" type="button">🔍 Search Database</button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" id="channels-tab" data-bs-toggle="tab" data-bs-target="#channels-panel" type="button" onclick="loadChannels()">📢 Channel Management</button>
                </li>
            </ul>

            <!-- TAB CONTENTS -->
            <div class="tab-content">
                
                <!-- TAB 1: LEAKS DATABASE -->
                <div class="tab-pane fade show active" id="live-panel">
                    <div class="card">
                        <div class="card-header border-secondary fw-bold">Captured Leaks & Intelligence</div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-dark table-hover mb-0 align-middle">
                                    <thead>
                                        <tr class="table-active">
                                            <th>ID</th>
                                            <th>Source Channel</th>
                                            <th>Message Content</th>
                                            <th>Indicators Matched</th>
                                            <th>Message Time</th>
                                        </tr>
                                    </thead>
                                    <tbody id="leaksTableBody">
                                        <tr><td colspan="5" class="text-center py-4 text-muted">Loading recorded leaks...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 2: KEYWORD SEARCH -->
                <div class="tab-pane fade" id="query-panel">
                    <div class="card mb-4">
                        <div class="card-header border-secondary fw-bold">🔍 Search Stored Messages</div>
                        <div class="card-body">
                            <div class="row g-3">
                                <div class="col-md-9">
                                    <input type="text" id="simpleKeyword" class="form-control bg-dark text-white border-secondary" placeholder="Type keyword to search (e.g. nadra, passport, darkweb, database)">
                                </div>
                                <div class="col-md-3">
                                    <button onclick="executeKeywordSearch()" class="btn btn-primary w-100">Search MySQL DB</button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header border-secondary fw-bold">Search Results</div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-dark table-hover mb-0 align-middle">
                                    <thead>
                                        <tr class="table-active">
                                            <th>Channel</th>
                                            <th>Message</th>
                                            <th>Targets</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="searchResultsBody">
                                        <tr><td colspan="4" class="text-center py-4 text-muted">Enter a search query above.</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 3: ADD & MANAGE CHANNELS -->
                <div class="tab-pane fade" id="channels-panel">
                    <div class="row">
                        <div class="col-md-5">
                            <div class="card mb-4">
                                <div class="card-header border-secondary fw-bold">➕ Join & Add New Telegram Channel</div>
                                <div class="card-body">
                                    <div class="mb-3">
                                        <label class="form-label text-muted">Telegram Link or Invite Code</label>
                                        <input type="text" id="channelLink" class="form-control bg-dark text-white border-secondary" placeholder="https://t.me/example_channel OR +joinchat_hash">
                                    </div>
                                    <button class="btn btn-success w-100" onclick="addChannel()">Join & Add Channel</button>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-7">
                            <div class="card">
                                <div class="card-header border-secondary fw-bold">📢 Monitored Channels Registry</div>
                                <div class="card-body p-0">
                                    <div class="table-responsive">
                                        <table class="table table-dark table-hover mb-0 align-middle">
                                            <thead>
                                                <tr class="table-active">
                                                    <th>Channel Title</th>
                                                    <th>Handle/Identifier</th>
                                                    <th>Channel ID</th>
                                                </tr>
                                            </thead>
                                            <tbody id="channelsTableBody">
                                                <tr><td colspan="3" class="text-center py-3 text-muted">Loading channels...</td></tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <div class="system-log" id="systemLog">[CORE] Security engine initialized — awaiting telemetry...</div>
        <script>
            let engineRunning=true, refreshTimer, animationFrame;
            const canvas=document.getElementById('cyberCanvas'),ctx=canvas.getContext('2d'),particles=[];
            function sizeCanvas(){canvas.width=innerWidth*devicePixelRatio;canvas.height=innerHeight*devicePixelRatio;canvas.style.width=innerWidth+'px';canvas.style.height=innerHeight+'px';ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
            function seedParticles(){particles.length=0;const n=Math.min(115,Math.floor(innerWidth/11));for(let i=0;i<n;i++)particles.push({x:Math.random()*innerWidth,y:Math.random()*innerHeight,z:Math.random()*2+.3,vx:(Math.random()-.5)*.25,vy:(Math.random()-.5)*.25})}
            function drawCore(t=0){if(!engineRunning)return;ctx.clearRect(0,0,innerWidth,innerHeight);const cx=innerWidth*.73,cy=innerHeight*.28,p=1+Math.sin(t*.0018)*.06,g=ctx.createRadialGradient(cx,cy,0,cx,cy,250);g.addColorStop(0,'rgba(0,234,255,.17)');g.addColorStop(.4,'rgba(138,92,255,.07)');g.addColorStop(1,'transparent');ctx.fillStyle=g;ctx.fillRect(cx-260,cy-260,520,520);ctx.save();ctx.translate(cx,cy);ctx.rotate(t*.00012);ctx.scale(p,p);for(let r=45;r<=155;r+=36){ctx.beginPath();ctx.arc(0,0,r,0,Math.PI*1.55);ctx.strokeStyle=r%2?'rgba(0,234,255,.35)':'rgba(138,92,255,.3)';ctx.stroke()}for(let i=0;i<8;i++){ctx.rotate(Math.PI/4);ctx.beginPath();ctx.moveTo(70,0);ctx.lineTo(155,0);ctx.strokeStyle='rgba(0,234,255,.2)';ctx.stroke()}ctx.restore();particles.forEach((a,i)=>{a.x+=a.vx*a.z;a.y+=a.vy*a.z;if(a.x<0||a.x>innerWidth)a.vx*=-1;if(a.y<0||a.y>innerHeight)a.vy*=-1;ctx.fillStyle=i%7===0?'rgba(255,43,214,.75)':'rgba(0,234,255,.6)';ctx.fillRect(a.x,a.y,a.z,a.z)});animationFrame=requestAnimationFrame(drawCore)}
            function logSystem(m){document.getElementById('systemLog').textContent='[CORE] '+m}
            function startEngine(){if(engineRunning)return;engineRunning=true;document.body.classList.remove('engine-off');document.querySelector('#engineState b').textContent='ENGINE ONLINE';seedParticles();drawCore();refreshData();refreshTimer=setInterval(refreshData,30000);logSystem('Engine started — live scan and visual telemetry active.')}
            function stopEngine(){engineRunning=false;document.body.classList.add('engine-off');document.querySelector('#engineState b').textContent='ENGINE STANDBY';cancelAnimationFrame(animationFrame);clearInterval(refreshTimer);ctx.clearRect(0,0,innerWidth,innerHeight);logSystem('Engine paused — stored intelligence remains available.')}
            addEventListener('resize',()=>{sizeCanvas();seedParticles()});sizeCanvas();seedParticles();drawCore();refreshTimer=setInterval(()=>{if(engineRunning)refreshData()},30000);
            function formatDate(rawDateStr) {
                if (!rawDateStr || rawDateStr === "undefined") return "N/A";
                const parsed = Date.parse(rawDateStr);
                if (isNaN(parsed)) return rawDateStr;
                return new Date(parsed).toLocaleString();
            }

            function renderRows(rows, showId = true) {
                if (!rows || rows.length === 0) return `<tr><td colspan="${showId ? 5 : 4}" class="text-center py-3 text-muted">No records found.</td></tr>`;
                
                return rows.map(leak => {
                    const entities = (leak.detected_entities || []).map(e => `<span class="badge badge-entity me-1">${e}</span>`).join('');
                    const domains = (leak.detected_domains || []).map(d => `<span class="badge badge-domain me-1">${d}</span>`).join('');
                    const idCol = showId ? `<td><span class="badge bg-secondary">${leak.id}</span></td>` : '';

                    return `
                        <tr>
                            ${idCol}
                            <td><strong class="text-info">@${leak.channel}</strong></td>
                            <td class="msg-box">${leak.text || ''}</td>
                            <td>${entities} ${domains}</td>
                            <td><small class="text-white">${formatDate(leak.message_date || leak.processed_at)}</small></td>
                        </tr>
                    `;
                }).join('');
            }

            async function loadLeaks() {
                try {
                    const res = await fetch('/leaks?limit=500');
                    const leaks = await res.json();
                    document.getElementById('leaksTableBody').innerHTML = renderRows(leaks, true);
                    document.getElementById('statLeaks').textContent = String(leaks.length).padStart(3, '0');
                    logSystem(`${leaks.length} intelligence records synchronized.`);
                } catch(e) { console.error(e); }
            }

            async function executeKeywordSearch() {
                try {
                    const word = document.getElementById('simpleKeyword').value;
                    const res = await fetch(`/search-leaks?keyword=${encodeURIComponent(word)}`);
                    const leaks = await res.json();
                    document.getElementById('searchResultsBody').innerHTML = renderRows(leaks, false);
                } catch(e) { console.error(e); }
            }

            async function loadChannels() {
                try {
                    const res = await fetch('/channels');
                    const channels = await res.json();
                    document.getElementById('statChannels').textContent = String((channels || []).length).padStart(2, '0');
                    if (!channels || channels.length === 0) {
                        document.getElementById('channelsTableBody').innerHTML = `<tr><td colspan="3" class="text-center py-3 text-muted">No channels added yet.</td></tr>`;
                        return;
                    }
                    document.getElementById('channelsTableBody').innerHTML = channels.map(c => `
                        <tr>
                            <td><strong>${c.title}</strong></td>
                            <td><span class="text-info">@${c.handle}</span></td>
                            <td><code>${c.channel_id}</code></td>
                        </tr>
                    `).join('');
                } catch(e) { console.error(e); }
            }

            async function addChannel() {
                const link = document.getElementById('channelLink').value.trim();
                if (!link) return alert("Please enter a valid channel link or handle.");
                
                try {
                    const res = await fetch('/add-channel', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ link })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        alert(`Successfully added channel: ${data.title}`);
                        document.getElementById('channelLink').value = '';
                        loadChannels();
                    } else {
                        alert(`Error: ${data.detail}`);
                    }
                } catch(e) { alert("Failed to add channel."); }
            }

            function refreshData() {
                loadLeaks();
                loadChannels();
            }

            loadLeaks();
            loadChannels();
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8101)
