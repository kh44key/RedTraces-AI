"""Create the database schema."""

import asyncio

from common.db import engine, init_db


async def main() -> None:
    try:
        await init_db()
        print("Database initialized; collected_messages table is ready.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
