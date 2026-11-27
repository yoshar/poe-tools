"""The Garish Power: is turning in a set of 4 cards worth more than selling them?

The card gives one random unique jewel from a fixed list, and every outcome is equally likely,
so the expected value of a turn-in is the plain average of the outcome prices.
"""
from dataclasses import asdict, dataclass, field
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ItemPrice, League, Patch

CARD_NAME = "The Garish Power"
CARDS_PER_SET = 4


@dataclass
class JewelRow:
    name: str
    base_type: str
    chaos: float | None
    listing_count: int | None
    warnings: list[str] = field(default_factory=list)
    share: float | None = None
    beats_cost: bool | None = None


@dataclass
class Evaluation:
    league: str
    card_price_ninja: float | None
    card_volume_chaos: float | None
    card_price_used: float | None
    card_price_overridden: bool
    card_warnings: list[str]
    cards_per_set: int
    chaos_per_divine: float | None
    prices_updated_at: str | None
    jewels: list[JewelRow]
    missing: list[str]
    cost: float | None = None
    avg_value: float | None = None
    median_value: float | None = None
    profit: float | None = None
    roi: float | None = None
    break_even_card_price: float | None = None
    chance_beats_cost: float | None = None
    avg_excluding_top: float | None = None
    top_jewel_share: float | None = None
    verdict: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def jewel_warnings(chaos: float | None, listings: int | None) -> list[str]:
    w = []
    if listings is not None and listings < settings.low_listing_threshold:
        w.append(f"Only {listings} listings, so this price is unreliable")
    if chaos is not None and chaos <= settings.price_floor_chaos:
        w.append("At poe.ninja's price floor, so it may not actually sell")
    return w


def card_warnings(volume: float | None) -> list[str]:
    if volume is not None and volume < settings.low_card_volume_chaos:
        return [f"Low trade volume ({volume:,.0f}c), so the ninja price may be off"]
    return []


def evaluate(
    league: str,
    outcomes: list[tuple[str, str]],
    jewel_prices: dict[str, tuple[float | None, int | None]],
    card_price_ninja: float | None,
    card_volume_chaos: float | None = None,
    card_price_override: float | None = None,
    chaos_per_divine: float | None = None,
    prices_updated_at: str | None = None,
    cards_per_set: int = CARDS_PER_SET,
) -> Evaluation:
    """Pure calculation; `jewel_prices` maps jewel name -> (chaos value, listing count)."""
    rows, missing = [], []
    for name, base in outcomes:
        if name in jewel_prices:
            chaos, listings = jewel_prices[name]
            rows.append(JewelRow(name, base, chaos, listings, jewel_warnings(chaos, listings)))
        else:
            missing.append(name)
            rows.append(JewelRow(name, base, None, None, ["No poe.ninja price in this league"]))

    used = card_price_override if card_price_override is not None else card_price_ninja
    ev = Evaluation(
        league=league,
        card_price_ninja=card_price_ninja,
        card_volume_chaos=card_volume_chaos,
        card_price_used=used,
        card_price_overridden=card_price_override is not None,
        card_warnings=card_warnings(card_volume_chaos) if card_price_override is None else [],
        cards_per_set=cards_per_set,
        chaos_per_divine=chaos_per_divine,
        prices_updated_at=prices_updated_at,
        jewels=sorted(rows, key=lambda r: -(r.chaos if r.chaos is not None else -1)),
        missing=missing,
    )

    values = [r.chaos for r in rows if r.chaos is not None]
    if not values:
        return ev
    total = sum(values)
    ev.avg_value = mean(values)
    ev.median_value = median(values)
    ev.break_even_card_price = ev.avg_value / cards_per_set
    ev.avg_excluding_top = (total - max(values)) / (len(values) - 1) if len(values) > 1 else None
    ev.top_jewel_share = max(values) / total if total else None
    for r in rows:
        if r.chaos is not None and total:
            r.share = r.chaos / total

    if used is not None:
        ev.cost = used * cards_per_set
        ev.profit = ev.avg_value - ev.cost
        ev.roi = ev.profit / ev.cost if ev.cost else None
        ev.chance_beats_cost = sum(1 for v in values if v >= ev.cost) / len(values)
        for r in rows:
            if r.chaos is not None:
                r.beats_cost = r.chaos >= ev.cost
        ev.verdict = "Profitable on average" if ev.profit > 0 else "Not profitable on average"
    return ev


# ------------------------------------------------------------ database glue


def current_outcomes(session: Session) -> list[tuple[str, str]]:
    patch = session.scalar(select(Patch).where(Patch.is_current))
    if patch is None:
        return []
    return [(o.name, o.base_type) for o in patch.garish_outcomes]


def pick_jewel_prices(rows: list[ItemPrice], wanted: set[str]) -> dict[str, tuple[float | None, int | None]]:
    """Plain (non-Foulborn, uncorrupted, no variant) copy of each wanted jewel.

    Foulborn jewels are listed under their own name ("Foulborn X"), so matching the exact name already
    leaves them out. If several plain lines exist, the one with the most listings wins.
    """
    best: dict[str, ItemPrice] = {}
    for r in rows:
        if r.name not in wanted or r.corrupted or r.variant:
            continue
        cur = best.get(r.name)
        if cur is None or (r.listing_count or 0) > (cur.listing_count or 0):
            best[r.name] = r
    return {n: (r.chaos_value, r.listing_count) for n, r in best.items()}


def evaluate_for_league(session: Session, league_id: str, card_price_override: float | None = None) -> Evaluation | None:
    league = session.get(League, league_id)
    if league is None:
        return None
    outcomes = current_outcomes(session)
    wanted = {n for n, _ in outcomes}
    jewels = list(
        session.scalars(
            select(ItemPrice).where(
                ItemPrice.league_id == league_id, ItemPrice.category == "UniqueJewel", ItemPrice.name.in_(wanted)
            )
        )
    )
    card = session.scalar(
        select(ItemPrice).where(
            ItemPrice.league_id == league_id, ItemPrice.category == "DivinationCard", ItemPrice.name == CARD_NAME
        )
    )
    return evaluate(
        league=league.id,
        outcomes=outcomes,
        jewel_prices=pick_jewel_prices(jewels, wanted),
        card_price_ninja=card.chaos_value if card else None,
        card_volume_chaos=card.volume_chaos if card else None,
        card_price_override=card_price_override,
        chaos_per_divine=league.chaos_per_divine,
        prices_updated_at=league.prices_updated_at.isoformat() if league.prices_updated_at else None,
    )
