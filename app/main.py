import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import NeedsLogin, is_admin
from .config import settings
from .db import SessionLocal
from .routers import admin, public
from .seed import seed_if_empty
from .templating import templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as session:
        seed_if_empty(session)
    sched = None
    if settings.run_scheduler:
        from .scheduler import start_scheduler

        sched = start_scheduler()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="PoE Tools", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
app.include_router(public.router)
app.include_router(admin.router)

templates.env.globals["is_admin"] = is_admin


@app.exception_handler(NeedsLogin)
async def needs_login(request: Request, exc: NeedsLogin):
    return RedirectResponse("/admin/login", status_code=303)
