"""Keep the advanced Telegram pipeline healthy until it is configured.

The supplied collector correctly requires a Telegram user session.  This
small entrypoint makes that requirement explicit without taking down the
combined local stack when credentials or approved channels are not configured.
"""

import os
import runpy
import time


def configured() -> bool:
    return bool(
        os.getenv("TELEGRAM_API_ID", "").strip()
        and os.getenv("TELEGRAM_API_HASH", "").strip()
        and os.getenv("TELEGRAM_CHANNELS", "").strip()
    )


if not configured():
    print(
        "RedTraces Telegram pipeline is standing by. Set TELEGRAM_API_ID, "
        "TELEGRAM_API_HASH, and REDTRACES_TELEGRAM_CHANNELS in .env, then "
        "recreate redtraces-telegram.",
        flush=True,
    )
    while True:
        time.sleep(3600)

runpy.run_module("collectors.telegram_collector", run_name="__main__")
