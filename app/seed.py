"""Starting game data, loaded once into an empty database."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GarishOutcome, Patch

# From the original spreadsheet: PoE Wiki unique jewels with drop enabled and not drop restricted,
# matching the 14 outcomes on The Garish Power wiki page.
GARISH_OUTCOMES = [
    ("Unnatural Instinct", "Viridian Jewel"),
    ("Stormshroud", "Viridian Jewel"),
    ("Inspired Learning", "Crimson Jewel"),
    ("Intuitive Leap", "Viridian Jewel"),
    ("Bloodnotch", "Crimson Jewel"),
    ("Immutable Force", "Crimson Jewel"),
    ("Ancestral Vision", "Viridian Jewel"),
    ("Unending Hunger", "Cobalt Jewel"),
    ("Might of the Meek", "Crimson Jewel"),
    ("Lioneye's Fall", "Viridian Jewel"),
    ("Pure Talent", "Viridian Jewel"),
    ("Firesong", "Crimson Jewel"),
    ("Witchbane", "Cobalt Jewel"),
    ("Dead Reckoning", "Cobalt Jewel"),
]


def seed_if_empty(session: Session) -> None:
    if session.scalar(select(Patch.id).limit(1)) is not None:
        return
    patch = Patch(name="Covens", is_current=True, notes="Initial data from the Garish Power spreadsheet.")
    patch.garish_outcomes = [GarishOutcome(name=n, base_type=b) for n, b in GARISH_OUTCOMES]
    session.add(patch)
    session.commit()
