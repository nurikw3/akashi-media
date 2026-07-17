"""Four-hour data-center digest worker.

The start-up check establishes a baseline: current articles are saved but not
published. Every following interval publishes only URLs not seen before.
Manual Telegram runs remain immediate and use the same durable history.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import DigestSettings, build_digest_container
from src.domain.errors import DomainError

logger = logging.getLogger(__name__)
CHECK_INTERVAL_HOURS = 4


async def check_for_new_posts(container) -> None:
    """Persist an initial baseline once, then publish genuinely new items."""
    repository = container.command.digest_repository
    try:
        if not repository.has_runs():
            report = await container.command.execute(
                limit=container.settings.post_limit,
                trigger="baseline",
                publish=False,
            )
            logger.info("Digest baseline recorded: %s candidates", report.candidates)
            return

        report = await container.command.execute(
            limit=container.settings.post_limit,
            trigger="scheduled",
        )
        logger.info(
            "Digest check completed: %s published, %s failed", report.published, report.failed
        )
    except DomainError:
        logger.exception("Digest check failed due to a domain error")
    except Exception:  # noqa: BLE001 - long-running worker must remain alive
        logger.exception("Unexpected digest worker failure")


async def run() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    container = build_digest_container(DigestSettings.from_env())
    # Establish the no-publish baseline on process start. The interval below
    # remains exactly four hours, while manual runs are safe immediately.
    await check_for_new_posts(container)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        check_for_new_posts,
        trigger="interval",
        hours=CHECK_INTERVAL_HOURS,
        args=(container,),
        id="data-center-digest",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Digest worker started; checks run every %s hours", CHECK_INTERVAL_HOURS)
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await container.aclose()
        await container.bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
