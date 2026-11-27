"""Settings, read from environment variables."""
import os
from dataclasses import dataclass


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/poetools")
    # Railway and most hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    admin_password: str | None
    ninja_base_url: str
    ninja_user_agent: str
    fetch_interval_minutes: int
    run_scheduler: bool
    # Price-quality thresholds for warnings.
    low_listing_threshold: int
    price_floor_chaos: float
    low_card_volume_chaos: float
    # History: keep every hourly point this many days, then thin to one point per day.
    history_full_days: int


def load_settings() -> Settings:
    return Settings(
        database_url=_db_url(),
        secret_key=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        admin_password=os.environ.get("ADMIN_PASSWORD") or None,
        ninja_base_url=os.environ.get("NINJA_BASE_URL", "https://poe.ninja"),
        ninja_user_agent=os.environ.get(
            "NINJA_USER_AGENT", "poe-tools/0.1 (personal Path of Exile analysis site)"
        ),
        fetch_interval_minutes=int(os.environ.get("FETCH_INTERVAL_MINUTES", "30")),
        run_scheduler=_bool("RUN_SCHEDULER", True),
        low_listing_threshold=int(os.environ.get("LOW_LISTING_THRESHOLD", "10")),
        price_floor_chaos=float(os.environ.get("PRICE_FLOOR_CHAOS", "1")),
        low_card_volume_chaos=float(os.environ.get("LOW_CARD_VOLUME_CHAOS", "500")),
        history_full_days=int(os.environ.get("HISTORY_FULL_DAYS", "7")),
    )


settings = load_settings()
