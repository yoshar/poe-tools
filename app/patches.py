"""Creating and comparing patches of hand-maintained game data."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import GarishOutcome, Patch


def current_patch(session: Session) -> Patch | None:
    return session.scalar(select(Patch).where(Patch.is_current))


def copy_patch(session: Session, source: Patch, name: str, make_current: bool = True) -> Patch:
    new = Patch(name=name, copied_from_id=source.id, notes=f"Copied from {source.name}.")
    new.garish_outcomes = [GarishOutcome(name=o.name, base_type=o.base_type) for o in source.garish_outcomes]
    session.add(new)
    session.flush()
    if make_current:
        set_current(session, new)
    return new


def set_current(session: Session, patch: Patch) -> None:
    session.execute(update(Patch).values(is_current=False))
    patch.is_current = True


def garish_diff(patch: Patch, previous: Patch | None) -> dict[str, list[str]]:
    if previous is None:
        return {"added": [], "removed": []}
    now = {o.name for o in patch.garish_outcomes}
    before = {o.name for o in previous.garish_outcomes}
    return {"added": sorted(now - before), "removed": sorted(before - now)}
