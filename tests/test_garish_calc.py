import pytest

from app.seed import GARISH_OUTCOMES
from app.tools.garish import evaluate

# The original spreadsheet (Covens, 2026-11-15): card 64c, these jewel prices.
SHEET_PRICES = {
    "Unnatural Instinct": 1539, "Stormshroud": 630, "Inspired Learning": 350, "Intuitive Leap": 175,
    "Bloodnotch": 160, "Immutable Force": 141.6, "Ancestral Vision": 110, "Unending Hunger": 25,
    "Might of the Meek": 13, "Lioneye's Fall": 3, "Pure Talent": 2, "Firesong": 1, "Witchbane": 1,
    "Dead Reckoning": 1,
}


def sheet_eval(**kw):
    prices = {n: (p, 100) for n, p in SHEET_PRICES.items()}
    return evaluate("Covens", GARISH_OUTCOMES, prices, card_price_ninja=64, chaos_per_divine=153.9, **kw)


def test_matches_spreadsheet():
    ev = sheet_eval()
    assert ev.cost == 256
    assert ev.avg_value == pytest.approx(3151.6 / 14)
    assert ev.profit == pytest.approx(3151.6 / 14 - 256)
    assert ev.roi == pytest.approx((3151.6 / 14 - 256) / 256)
    assert ev.break_even_card_price == pytest.approx(3151.6 / 14 / 4)
    assert ev.median_value == pytest.approx((25 + 110) / 2)
    assert ev.chance_beats_cost == pytest.approx(3 / 14)  # 1539, 630 and 350 all beat 256
    assert ev.avg_excluding_top == pytest.approx((3151.6 - 1539) / 13)
    assert ev.verdict == "Not profitable on average"


def test_override_replaces_ninja_price():
    ev = sheet_eval(card_price_override=50)
    assert ev.card_price_overridden
    assert ev.card_price_ninja == 64
    assert ev.cost == 200
    assert ev.verdict == "Profitable on average"


def test_zero_override_is_respected():
    ev = sheet_eval(card_price_override=0)
    assert ev.cost == 0
    assert ev.roi is None


def test_weak_prices_flagged():
    prices = {n: (p, 100) for n, p in SHEET_PRICES.items()}
    prices["Unnatural Instinct"] = (1539, 3)
    ev = evaluate("Covens", GARISH_OUTCOMES, prices, card_price_ninja=64)
    by = {j.name: j for j in ev.jewels}
    assert any("listings" in w for w in by["Unnatural Instinct"].warnings)
    assert any("floor" in w for w in by["Firesong"].warnings)
    assert by["Stormshroud"].warnings == []


def test_low_card_volume_warning_only_without_override():
    prices = {n: (p, 100) for n, p in SHEET_PRICES.items()}
    ev = evaluate("Covens", GARISH_OUTCOMES, prices, card_price_ninja=64, card_volume_chaos=100)
    assert ev.card_warnings
    ev = evaluate("Covens", GARISH_OUTCOMES, prices, card_price_ninja=64, card_volume_chaos=100, card_price_override=60)
    assert ev.card_warnings == []


def test_missing_jewel_is_reported_and_left_out():
    prices = {n: (p, 100) for n, p in SHEET_PRICES.items() if n != "Stormshroud"}
    ev = evaluate("Covens", GARISH_OUTCOMES, prices, card_price_ninja=64)
    assert ev.missing == ["Stormshroud"]
    assert ev.avg_value == pytest.approx((3151.6 - 630) / 13)


def test_no_card_price_still_shows_jewels():
    prices = {n: (p, 100) for n, p in SHEET_PRICES.items()}
    ev = evaluate("Covens", GARISH_OUTCOMES, prices, card_price_ninja=None)
    assert ev.cost is None and ev.verdict is None
    assert ev.avg_value == pytest.approx(3151.6 / 14)
