"""Trimmed poe.ninja responses captured for Covens on 2026-11-27 (only the fields we use)."""


def _jewel(id_, name, base, chaos, listings, variant=None, corrupted=False):
    d = {"id": id_, "name": name, "baseType": base, "detailsId": name.lower().replace(" ", "-").replace("'", "") + "-" + base.lower().replace(" ", "-"),
         "chaosValue": chaos, "divineValue": round(chaos / 149.3, 2), "listingCount": listings, "count": 399}
    if variant:
        d["variant"] = variant
        d["detailsId"] += "-" + variant.lower().replace(" ", "-")
    if corrupted:
        d["corrupted"] = True
    return d


LEAGUES = [
    {"id": "Covens", "name": "Covens"},
    {"id": "Hardcore Covens", "name": "Hardcore Covens"},
    {"id": "Standard", "name": "Standard"},
    {"id": "Hardcore", "name": "Hardcore"},
]

UNIQUE_JEWELS = {
    "lines": [
        _jewel(100432, "Stormshroud", "Viridian Jewel", 849, 750),
        _jewel(7376, "Unnatural Instinct", "Viridian Jewel", 800, 1150),
        _jewel(676, "Inspired Learning", "Crimson Jewel", 33, 2347),
        _jewel(677, "Intuitive Leap", "Viridian Jewel", 29, 865),
        _jewel(4858, "Might of the Meek", "Crimson Jewel", 20, 672),
        _jewel(1745, "Unending Hunger", "Cobalt Jewel", 15, 925),
        _jewel(103486, "Ancestral Vision", "Viridian Jewel", 10, 1804),
        _jewel(100351, "Immutable Force", "Crimson Jewel", 7, 2504),
        _jewel(103434, "Bloodnotch", "Crimson Jewel", 3, 1908),
        _jewel(754, "Lioneye's Fall", "Viridian Jewel", 2, 761),
        _jewel(2284, "Pure Talent", "Viridian Jewel", 2, 932),
        _jewel(362, "Dead Reckoning", "Cobalt Jewel", 1, 518),
        _jewel(100353, "Firesong", "Crimson Jewel", 1, 638),
        _jewel(100439, "Witchbane", "Cobalt Jewel", 1, 553),
        # Must be ignored by the Garish Power tool:
        _jewel(9001, "Foulborn Unnatural Instinct", "Viridian Jewel", 313645, 3, variant="No Notables, Grant Notables"),
        _jewel(9002, "Unnatural Instinct", "Viridian Jewel", 5000, 2, corrupted=True),
    ]
}

DIVINATION_CARDS = {
    "core": {"primary": "chaos", "secondary": "divine", "rates": {"divine": 0.006696}},
    "items": [
        {"id": "the-garish-power", "name": "The Garish Power", "category": "Cards", "detailsId": "the-garish-power"},
        {"id": "the-doctor", "name": "The Doctor", "category": "Cards", "detailsId": "the-doctor"},
    ],
    "lines": [
        {"id": "the-garish-power", "primaryValue": 29.67, "volumePrimaryValue": 2759, "maxVolumeCurrency": "chaos", "maxVolumeRate": 0.0337},
        {"id": "the-doctor", "primaryValue": 5700, "volumePrimaryValue": 120000, "maxVolumeCurrency": "divine", "maxVolumeRate": 0.026},
    ],
}
