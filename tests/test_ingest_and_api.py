import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ingest import run_fetch
from app.models import ItemPrice, League, PriceHistory
from app.ninja import NinjaClient, parse_exchange_overview
from app.seed import seed_if_empty
from tests.conftest import fake_ninja_transport
from tests.fixtures import ninja as fx


def test_exchange_parse_converts_divine_rate():
    r = parse_exchange_overview(fx.DIVINATION_CARDS)
    assert r.chaos_per_divine == pytest.approx(1 / 0.006696)
    gp = next(l for l in r.lines if l.name == "The Garish Power")
    assert gp.chaos_value == 29.67 and gp.volume_chaos == 2759


def test_fetch_stores_every_league(session, ninja_client):
    log = run_fetch(session, ninja_client)
    assert log.ok, log.message
    assert session.scalar(select(func.count()).select_from(League)) == 4
    assert session.get(League, "Covens").chaos_per_divine == pytest.approx(149.34, rel=1e-3)
    n = session.scalar(select(func.count()).select_from(ItemPrice).where(ItemPrice.league_id == "Covens"))
    assert n == len(fx.UNIQUE_JEWELS["lines"]) + 2
    # A second run within the hour updates prices but adds no history rows.
    h1 = session.scalar(select(func.count()).select_from(PriceHistory))
    run_fetch(session, ninja_client)
    assert session.scalar(select(func.count()).select_from(PriceHistory)) == h1


def test_dropped_league_is_hidden(session):
    c = NinjaClient(transport=fake_ninja_transport())
    run_fetch(session, c)
    c2 = NinjaClient(transport=fake_ninja_transport(leagues=fx.LEAGUES[2:]))
    run_fetch(session, c2)
    assert session.get(League, "Covens").active is False
    assert session.get(League, "Standard").active is True


@pytest.fixture
def client(session, ninja_client):
    seed_if_empty(session)
    run_fetch(session, ninja_client)
    from app.main import app

    with TestClient(app) as tc:
        yield tc


def test_api_uses_plain_jewels_and_ninja_card_price(client):
    r = client.get("/api/tools/garish-power", params={"league": "Covens"})
    assert r.status_code == 200
    ev = r.json()
    ui = next(j for j in ev["jewels"] if j["name"] == "Unnatural Instinct")
    assert ui["chaos"] == 800  # not the Foulborn or corrupted lines
    assert ev["card_price_used"] == 29.67
    assert ev["cost"] == pytest.approx(118.68)
    assert ev["avg_value"] == pytest.approx(1773 / 14)
    assert ev["missing"] == []


def test_api_override_and_validation(client):
    ev = client.get("/api/tools/garish-power", params={"league": "Covens", "card_price": "40"}).json()
    assert ev["cost"] == 160 and ev["card_price_overridden"] is True
    assert client.get("/api/tools/garish-power", params={"league": "Covens", "card_price": "abc"}).status_code == 400
    assert client.get("/api/tools/garish-power", params={"league": "Nope"}).status_code == 404


def test_page_renders_and_redirects_to_first_league(client):
    r = client.get("/tools/garish-power", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("league=Covens")
    r = client.get("/tools/garish-power?league=Hardcore%20Covens")
    assert r.status_code == 200 and "The Garish Power" in r.text
    assert client.get("/").status_code == 200


def test_admin_requires_login_and_edits_patch(client):
    assert client.get("/admin", follow_redirects=False).headers["location"] == "/admin/login"
    assert client.post("/admin/login", data={"password": "wrong"}, follow_redirects=False).headers["location"].endswith("error=1")
    client.post("/admin/login", data={"password": "test-pass"})
    assert client.get("/admin").status_code == 200

    r = client.post("/admin/patches", data={"name": "3.28"}, follow_redirects=False)
    new_url = r.headers["location"]
    page = client.get(new_url).text
    assert "Unnatural Instinct" in page and "Changes since Covens" in page

    pid = new_url.rsplit("/", 1)[1]
    client.post(f"/admin/patches/{pid}/garish", data={"name": "New Jewel", "base_type": "Cobalt Jewel"})
    assert "+ New Jewel" in client.get(new_url).text
    ev = client.get("/api/tools/garish-power", params={"league": "Covens"}).json()
    assert "New Jewel" in ev["missing"]  # the new patch is current and has no price yet

    csv_text = client.get(f"/admin/patches/{pid}/garish.csv").text
    assert csv_text.splitlines()[0] == "name,base_type"
    client.post(f"/admin/patches/{pid}/garish.csv", files={"file": ("x.csv", "name,base_type\nWitchbane,Cobalt Jewel\n")})
    ev = client.get("/api/tools/garish-power", params={"league": "Covens"}).json()
    assert [j["name"] for j in ev["jewels"]] == ["Witchbane"]
