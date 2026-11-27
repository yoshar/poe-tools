# PoE Tools

Path of Exile (PoE1) analysis pages that update themselves from [poe.ninja](https://poe.ninja/docs/api) prices.

**Tools**
- **The Garish Power**: is turning in 4 cards for a random unique jewel worth more than selling them? Every
  outcome is equally likely, so the value of a turn-in is the plain average of the jewel prices. The card price
  defaults to poe.ninja and can be overridden on the page. Weak prices (fewer than 10 listings, or at the 1c
  floor) are flagged.

## How it works

- **FastAPI + Postgres.** One web process; a background job fetches poe.ninja every 30 minutes for every PoE1
  league it lists (leagues endpoint, Unique Jewel overview, Divination Card exchange).
- **Current prices** live in `item_prices`; **history** in `price_history` (hourly for 7 days, then one point per
  day).
- **Game data you maintain** (Garish Power outcomes now, scry map pools next) is grouped into **patches**. At the
  start of a league, open `/admin`, start a new patch (it copies the current one), and change what the patch notes
  changed. The patch page shows what changed since the previous patch, and lists can be exported/imported as CSV.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
createdb poetools
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/poetools ADMIN_PASSWORD=dev
alembic upgrade head
uvicorn app.main:app --reload
```

Tests need a `poetools_test` database: `createdb poetools_test && python -m pytest`.

After changing `app/models.py`, create a migration: `alembic revision --autogenerate -m "what changed"`.

## Settings (environment variables)

| Name | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | local Postgres | Postgres connection string (`postgres://` URLs from hosts are accepted) |
| `SECRET_KEY` | dev value | Signs the admin login cookie. **Set this in production.** |
| `ADMIN_PASSWORD` | unset | Password for `/admin`. Admin is off when unset. |
| `NINJA_USER_AGENT` | `poe-tools/0.1 (...)` | poe.ninja asks for a descriptive User-Agent; add a contact URL |
| `FETCH_INTERVAL_MINUTES` | 30 | How often to pull poe.ninja (its PoE1 data changes about every 15 min) |
| `RUN_SCHEDULER` | true | Turn off the background fetch (tests do) |
| `LOW_LISTING_THRESHOLD` | 10 | Fewer listings than this marks a price as weak |
| `PRICE_FLOOR_CHAOS` | 1 | Prices at or below this are flagged as at the floor |
| `LOW_CARD_VOLUME_CHAOS` | 500 | Card trade volume below this flags the ninja card price |
| `HISTORY_FULL_DAYS` | 7 | Days of hourly price history to keep before thinning to daily |

## Deploy on Railway

1. New project → **Deploy from GitHub repo** → `poe-tools`.
2. Add a **PostgreSQL** database to the project, then on the web service set `DATABASE_URL` to `${{Postgres.DATABASE_URL}}`.
3. Set `SECRET_KEY` (any long random string) and `ADMIN_PASSWORD`.
4. Under Networking, **Generate Domain**. `railway.json` runs migrations on each deploy and starts one worker.

Keep it at one worker/replica: the price fetch runs inside the web process.
