import asyncio

from shared.database import SessionLocal, init_db
from shared.purger import purge_old_slips


async def main() -> None:
    await init_db()
    async with SessionLocal() as session:
        deleted = await purge_old_slips(session)
        print(f"Purged {deleted} slip(s) older than retention window.")


if __name__ == "__main__":
    asyncio.run(main())
