import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/poetools_test")
os.environ["RUN_SCHEDULER"] = "false"
os.environ["ADMIN_PASSWORD"] = "test-pass"

import httpx
import pytest

from app.db import Base, SessionLocal, engine
from app.ninja import NinjaClient
from tests.fixtures import ninja as fx


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


def fake_ninja_transport(jewels=None, cards=None, leagues=None, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        assert request.headers["User-Agent"].startswith("poe-tools")
        path = request.url.path
        if path == "/poe1/api/economy/leagues":
            return httpx.Response(200, json=leagues if leagues is not None else fx.LEAGUES)
        t = request.url.params.get("type")
        if path.endswith("/stash/current/item/overview") and t == "UniqueJewel":
            return httpx.Response(200, json=jewels if jewels is not None else fx.UNIQUE_JEWELS, headers={"ETag": '"j1"'})
        if path.endswith("/exchange/current/overview") and t == "DivinationCard":
            return httpx.Response(200, json=cards if cards is not None else fx.DIVINATION_CARDS)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def ninja_client():
    c = NinjaClient(base_url="https://poe.ninja", transport=fake_ninja_transport())
    yield c
    c.close()
