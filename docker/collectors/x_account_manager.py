"""Multi-account helpers for the X / Twitter collector.

twscrape already ships an accounts pool that rotates requests and tracks
per-account rate limits, and it persists everything to accounts.db. This module
is a thin wrapper so the collector, the CLI and the dashboard all talk to that
same pool in a consistent shape.

Each helper builds its own AccountsPool: the scraping loop runs in a separate
thread with its own event loop, and sharing one aiosqlite handle across loops
is asking for trouble.
"""

from datetime import datetime, timezone
from pathlib import Path

from twscrape import AccountsPool

BASE_DIR = Path(__file__).resolve().parent
POOL_DB = "/data/accounts.db"


def get_pool():
    return AccountsPool(POOL_DB)


def cookie_string(auth_token, ct0):
    return "auth_token={}; ct0={}".format(auth_token.strip(), ct0.strip())


async def add_cookie_account(username, auth_token, ct0):
    """Register (or refresh) an X account from its session cookies."""
    pool = get_pool()
    await pool.add_account_cookies(username, cookie_string(auth_token, ct0))
    return username


async def remove_account(username):
    pool = get_pool()
    await pool.delete_accounts([username])
    return username


async def set_active(username, active):
    pool = get_pool()
    await pool.set_active(username, active)
    return username


def _lock_summary(locks):
    """Turn twscrape's per-endpoint locks into a short human-readable note."""
    if not locks:
        return None

    now = datetime.now(timezone.utc)
    waiting = []
    for endpoint, until in locks.items():
        if not until:
            continue
        try:
            moment = until
            if isinstance(until, str):
                moment = datetime.fromisoformat(until)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            if moment > now:
                waiting.append(
                    "{} for {}s".format(endpoint, int((moment - now).total_seconds()))
                )
        except Exception:
            continue

    return "rate limited: " + ", ".join(waiting) if waiting else None


async def pool_status():
    """One row per X account, shaped like the Telegram pool's /accounts."""
    pool = get_pool()
    accounts = await pool.get_all()

    report = []
    for account in accounts:
        locked = _lock_summary(getattr(account, "locks", None))
        error = getattr(account, "error_msg", None)

        if not account.active:
            status = "inactive"
        elif error:
            status = "error"
        elif locked:
            status = "cooling"
        else:
            status = "online"

        report.append(
            {
                "username": account.username,
                "status": status,
                "active": bool(account.active),
                "last_used": (
                    account.last_used.isoformat()
                    if getattr(account, "last_used", None)
                    else None
                ),
                "note": error or locked,
            }
        )

    return report

