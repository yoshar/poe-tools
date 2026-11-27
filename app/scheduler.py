import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .db import SessionLocal
from .ingest import run_fetch
from .ninja import NinjaClient

log = logging.getLogger(__name__)
_client: NinjaClient | None = None


def fetch_job() -> None:
    global _client
    if _client is None:
        _client = NinjaClient()
    with SessionLocal() as session:
        entry = run_fetch(session, _client)
        log.info("poe.ninja fetch ok=%s\n%s", entry.ok, entry.message)


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        fetch_job,
        "interval",
        minutes=settings.fetch_interval_minutes,
        next_run_time=datetime.now(timezone.utc),  # also run once at startup
        max_instances=1,
        coalesce=True,
        id="ninja_fetch",
    )
    sched.start()
    return sched
