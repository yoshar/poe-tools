"""Pull poe.ninja prices for every league into the database."""
import logging
from datetime import timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from .config import settings
from .models import FetchLog, ItemPrice, League, PriceHistory, utcnow
from .ninja import CATEGORIES, NinjaClient, NotModified

log = logging.getLogger(__name__)

HISTORY_MIN_GAP = timedelta(minutes=55)  # at most one history point per item per hour


def sync_leagues(session: Session, client: NinjaClient) -> list[League]:
    listed = client.leagues()
    seen = set()
    for i, lg in enumerate(listed):
        seen.add(lg["id"])
        row = session.get(League, lg["id"])
        if row is None:
            row = League(id=lg["id"], name=lg.get("name") or lg["id"])
            session.add(row)
        row.name = lg.get("name") or lg["id"]
        row.sort_order = i
        row.active = True
    for row in session.scalars(select(League)):
        if row.id not in seen:
            row.active = False
    session.flush()
    return list(session.scalars(select(League).where(League.active).order_by(League.sort_order)))


def _last_history_time(session: Session, league_id: str, category: str):
    return session.scalar(
        select(PriceHistory.recorded_at)
        .where(PriceHistory.league_id == league_id, PriceHistory.category == category)
        .order_by(PriceHistory.recorded_at.desc())
        .limit(1)
    )


def store_category(session: Session, league: League, category: str, result) -> int:
    now = utcnow()
    existing = {
        p.item_key: p
        for p in session.scalars(
            select(ItemPrice).where(ItemPrice.league_id == league.id, ItemPrice.category == category)
        )
    }
    last = _last_history_time(session, league.id, category)
    if last is not None and last.tzinfo is None:  # SQLite drops tz info
        last = last.replace(tzinfo=now.tzinfo)
    write_history = last is None or now - last >= HISTORY_MIN_GAP

    seen = set()
    for ln in result.lines:
        if ln.item_key in seen:
            continue
        seen.add(ln.item_key)
        row = existing.get(ln.item_key)
        if row is None:
            row = ItemPrice(league_id=league.id, category=category, item_key=ln.item_key)
            session.add(row)
        row.name = ln.name
        row.base_type = ln.base_type
        row.variant = ln.variant
        row.corrupted = ln.corrupted
        row.links = ln.links
        row.chaos_value = ln.chaos_value
        row.divine_value = ln.divine_value
        row.listing_count = ln.listing_count
        row.volume_chaos = ln.volume_chaos
        row.updated_at = now
        if write_history:
            session.add(
                PriceHistory(
                    league_id=league.id,
                    category=category,
                    item_key=ln.item_key,
                    recorded_at=now,
                    chaos_value=ln.chaos_value,
                    listing_count=ln.listing_count,
                    volume_chaos=ln.volume_chaos,
                )
            )
    # Items poe.ninja no longer lists are removed from "current" prices (history keeps them).
    for key, row in existing.items():
        if key not in seen:
            session.delete(row)
    if result.chaos_per_divine:
        league.chaos_per_divine = result.chaos_per_divine
    return len(seen)


def prune_history(session: Session) -> None:
    """Keep every point for history_full_days, then only the first point of each day."""
    cutoff = utcnow() - timedelta(days=settings.history_full_days)
    session.execute(
        text(
            """
            DELETE FROM price_history WHERE id IN (
              SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                  PARTITION BY league_id, category, item_key, date(recorded_at)
                  ORDER BY recorded_at) AS rn
                FROM price_history WHERE recorded_at < :cutoff
              ) t WHERE rn > 1
            )
            """
        ),
        {"cutoff": cutoff},
    )


def run_fetch(session: Session, client: NinjaClient) -> FetchLog:
    entry = FetchLog(started_at=utcnow())
    session.add(entry)
    session.commit()
    notes = []
    ok = True
    try:
        leagues = sync_leagues(session, client)
        session.commit()
        for league in leagues:
            changed = False
            for category, kind in CATEGORIES:
                try:
                    result = client.category(league.id, category, kind)
                except NotModified:
                    continue
                except Exception as exc:  # one bad category shouldn't stop the rest
                    ok = False
                    notes.append(f"{league.id}/{category}: {exc}")
                    log.exception("fetch failed for %s/%s", league.id, category)
                    session.rollback()
                    continue
                n = store_category(session, league, category, result)
                changed = True
                notes.append(f"{league.id}/{category}: {n} items")
            if changed:
                league.prices_updated_at = utcnow()
            session.commit()
        prune_history(session)
        session.commit()
    except Exception as exc:
        ok = False
        session.rollback()
        notes.append(f"fatal: {exc}")
        log.exception("fetch run failed")
    entry = session.merge(entry)
    entry.finished_at = utcnow()
    entry.ok = ok
    entry.message = "\n".join(notes)
    session.commit()
    # Keep the log short.
    old = select(FetchLog.id).order_by(FetchLog.id.desc()).offset(200)
    session.execute(delete(FetchLog).where(FetchLog.id.in_(old.scalar_subquery())))
    session.commit()
    return entry
