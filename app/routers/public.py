from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_session
from ..models import League
from ..templating import templates
from ..tools import garish

router = APIRouter()

TOOLS = [
    {
        "slug": "garish-power",
        "name": "The Garish Power",
        "summary": "Is turning in 4 cards for a random unique jewel worth more than selling the cards?",
    },
]


def active_leagues(session: Session) -> list[League]:
    return list(session.scalars(select(League).where(League.active).order_by(League.sort_order)))


def _parse_price(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        v = float(raw)
    except ValueError:
        raise HTTPException(400, "card_price must be a number")
    if v < 0:
        raise HTTPException(400, "card_price must not be negative")
    return v


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"tools": TOOLS})


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/api/leagues")
def api_leagues(session: Session = Depends(get_session)):
    return [
        {
            "id": lg.id,
            "name": lg.name,
            "chaos_per_divine": lg.chaos_per_divine,
            "prices_updated_at": lg.prices_updated_at.isoformat() if lg.prices_updated_at else None,
        }
        for lg in active_leagues(session)
    ]


@router.get("/api/tools/garish-power")
def api_garish(
    league: str = Query(...),
    card_price: str | None = Query(None, description="Override the poe.ninja card price (chaos)"),
    session: Session = Depends(get_session),
):
    ev = garish.evaluate_for_league(session, league, _parse_price(card_price))
    if ev is None:
        raise HTTPException(404, f"Unknown league {league!r}")
    return ev.to_dict()


@router.get("/tools/garish-power", response_class=HTMLResponse)
def garish_page(
    request: Request,
    league: str | None = None,
    card_price: str | None = None,
    session: Session = Depends(get_session),
):
    leagues = active_leagues(session)
    if not leagues:
        return templates.TemplateResponse(request, "garish.html", {"leagues": [], "league": None, "ev": None})
    ids = [lg.id for lg in leagues]
    if league not in ids:
        return RedirectResponse(f"/tools/garish-power?league={ids[0]}", status_code=302)
    ev = garish.evaluate_for_league(session, league, _parse_price(card_price))
    return templates.TemplateResponse(
        request,
        "garish.html",
        {
            "leagues": leagues,
            "league": league,
            "ev": ev.to_dict(),
            "thresholds": {
                "low_listings": settings.low_listing_threshold,
                "floor": settings.price_floor_chaos,
            },
        },
    )
