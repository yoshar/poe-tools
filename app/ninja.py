"""Small poe.ninja client (PoE1 economy endpoints only).

Docs: https://poe.ninja/docs/api. poe.ninja asks clients to set a descriptive User-Agent, respect its
caching (ETag), and not poll faster than the data changes (~15 minutes for PoE1).
"""
from dataclasses import dataclass

import httpx

from .config import settings

# Categories to fetch for every league. kind "item" = stash item overview, "exchange" = exchange overview.
CATEGORIES: list[tuple[str, str]] = [
    ("UniqueJewel", "item"),
    ("DivinationCard", "exchange"),
]


@dataclass
class PriceLine:
    item_key: str
    name: str
    base_type: str | None
    variant: str | None
    corrupted: bool
    links: int | None
    chaos_value: float | None
    divine_value: float | None
    listing_count: int | None
    volume_chaos: float | None


@dataclass
class CategoryResult:
    lines: list[PriceLine]
    chaos_per_divine: float | None = None


class NotModified(Exception):
    pass


class NinjaClient:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(
            base_url=base_url or settings.ninja_base_url,
            headers={"User-Agent": settings.ninja_user_agent, "Accept": "application/json"},
            timeout=30,
            transport=transport,
        )
        self._etags: dict[str, str] = {}

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, params: dict | None = None, use_etag: bool = True):
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
        headers = {}
        if use_etag and key in self._etags:
            headers["If-None-Match"] = self._etags[key]
        r = self._http.get(path, params=params, headers=headers)
        if r.status_code == 304:
            raise NotModified(key)
        r.raise_for_status()
        if etag := r.headers.get("ETag"):
            self._etags[key] = etag
        return r.json()

    def leagues(self) -> list[dict]:
        return self._get("/poe1/api/economy/leagues", use_etag=False)

    def category(self, league: str, category: str, kind: str) -> CategoryResult:
        if kind == "item":
            data = self._get("/poe1/api/economy/stash/current/item/overview", {"league": league, "type": category})
            return parse_item_overview(data)
        if kind == "exchange":
            data = self._get("/poe1/api/economy/exchange/current/overview", {"league": league, "type": category})
            return parse_exchange_overview(data)
        raise ValueError(f"unknown kind {kind}")


def _item_key(line: dict) -> str:
    key = line.get("detailsId") or str(line.get("id"))
    if line.get("variant"):
        key += "|v:" + line["variant"]
    if line.get("links"):
        key += f"|l:{line['links']}"
    if line.get("corrupted"):
        key += "|corrupted"
    return key


def parse_item_overview(data: dict) -> CategoryResult:
    lines = []
    for ln in data.get("lines", []):
        lines.append(
            PriceLine(
                item_key=_item_key(ln),
                name=ln["name"],
                base_type=ln.get("baseType"),
                variant=ln.get("variant") or None,
                corrupted=bool(ln.get("corrupted")),
                links=ln.get("links") or None,
                chaos_value=ln.get("chaosValue"),
                divine_value=ln.get("divineValue"),
                listing_count=ln.get("listingCount"),
                volume_chaos=None,
            )
        )
    return CategoryResult(lines=lines)


def parse_exchange_overview(data: dict) -> CategoryResult:
    core = data.get("core") or {}
    rates = core.get("rates") or {}
    primary = core.get("primary")
    # rates[x] = how many x one unit of the primary currency buys.
    if primary == "chaos":
        to_chaos = 1.0
    elif primary and rates.get("chaos"):
        to_chaos = float(rates["chaos"])
    else:
        raise ValueError(f"exchange overview has primary currency {primary!r} and no chaos rate")
    divine_rate = rates.get("divine")  # divines per primary unit
    chaos_per_divine = (1.0 / float(divine_rate)) * to_chaos if divine_rate else None

    names = {it["id"]: it for it in data.get("items", [])}
    lines = []
    for ln in data.get("lines", []):
        meta = names.get(ln["id"])
        if not meta:
            continue
        value = ln.get("primaryValue")
        chaos = value * to_chaos if value is not None else None
        vol = ln.get("volumePrimaryValue")
        lines.append(
            PriceLine(
                item_key=ln["id"],
                name=meta["name"],
                base_type=None,
                variant=None,
                corrupted=False,
                links=None,
                chaos_value=chaos,
                divine_value=(chaos / chaos_per_divine) if (chaos is not None and chaos_per_divine) else None,
                listing_count=None,
                volume_chaos=vol * to_chaos if vol is not None else None,
            )
        )
    return CategoryResult(lines=lines, chaos_per_divine=chaos_per_divine)
