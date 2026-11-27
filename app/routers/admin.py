"""Admin pages for hand-maintained game data. Protected by ADMIN_PASSWORD."""
import csv
import io

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import check_password, require_admin
from ..db import get_session
from ..ingest import run_fetch
from ..models import FetchLog, GarishOutcome, League, Patch
from ..patches import copy_patch, current_patch, garish_diff, set_current
from ..ninja import NinjaClient
from ..templating import templates

router = APIRouter(prefix="/admin")


def _back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str | None = None):
    return templates.TemplateResponse(request, "admin/login.html", {"error": error})


@router.post("/login")
def login(request: Request, password: str = Form(...)):
    if not check_password(password):
        return _back("/admin/login?error=1")
    request.session["admin"] = True
    return _back("/admin")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return _back("/")


@router.get("", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def dashboard(request: Request, session: Session = Depends(get_session)):
    patches = list(session.scalars(select(Patch).order_by(Patch.created_at.desc())))
    logs = list(session.scalars(select(FetchLog).order_by(FetchLog.id.desc()).limit(10)))
    leagues = list(session.scalars(select(League).order_by(League.active.desc(), League.sort_order)))
    return templates.TemplateResponse(
        request, "admin/dashboard.html", {"patches": patches, "logs": logs, "leagues": leagues}
    )


@router.post("/fetch-now", dependencies=[Depends(require_admin)])
def fetch_now(session: Session = Depends(get_session)):
    client = NinjaClient()
    try:
        run_fetch(session, client)
    finally:
        client.close()
    return _back("/admin")


@router.post("/patches", dependencies=[Depends(require_admin)])
def new_patch(name: str = Form(...), session: Session = Depends(get_session)):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    source = current_patch(session)
    if source is None:
        patch = Patch(name=name, is_current=True)
        session.add(patch)
    else:
        patch = copy_patch(session, source, name)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(400, f"A patch named {name!r} already exists")
    return _back(f"/admin/patches/{patch.id}")


def _get_patch(session: Session, patch_id: int) -> Patch:
    patch = session.get(Patch, patch_id)
    if patch is None:
        raise HTTPException(404, "No such patch")
    return patch


@router.get("/patches/{patch_id}", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def patch_page(request: Request, patch_id: int, session: Session = Depends(get_session)):
    patch = _get_patch(session, patch_id)
    previous = session.get(Patch, patch.copied_from_id) if patch.copied_from_id else None
    return templates.TemplateResponse(
        request,
        "admin/patch.html",
        {"patch": patch, "previous": previous, "diff": garish_diff(patch, previous)},
    )


@router.post("/patches/{patch_id}/current", dependencies=[Depends(require_admin)])
def make_current(patch_id: int, session: Session = Depends(get_session)):
    set_current(session, _get_patch(session, patch_id))
    session.commit()
    return _back(f"/admin/patches/{patch_id}")


@router.post("/patches/{patch_id}/notes", dependencies=[Depends(require_admin)])
def save_notes(patch_id: int, notes: str = Form(""), session: Session = Depends(get_session)):
    _get_patch(session, patch_id).notes = notes
    session.commit()
    return _back(f"/admin/patches/{patch_id}")


@router.post("/patches/{patch_id}/garish", dependencies=[Depends(require_admin)])
def add_outcome(
    patch_id: int, name: str = Form(...), base_type: str = Form(""), session: Session = Depends(get_session)
):
    patch = _get_patch(session, patch_id)
    name = name.strip()
    if name and name not in {o.name for o in patch.garish_outcomes}:
        patch.garish_outcomes.append(GarishOutcome(name=name, base_type=base_type.strip()))
        session.commit()
    return _back(f"/admin/patches/{patch_id}")


@router.post("/patches/{patch_id}/garish/{outcome_id}/delete", dependencies=[Depends(require_admin)])
def remove_outcome(patch_id: int, outcome_id: int, session: Session = Depends(get_session)):
    outcome = session.get(GarishOutcome, outcome_id)
    if outcome and outcome.patch_id == patch_id:
        session.delete(outcome)
        session.commit()
    return _back(f"/admin/patches/{patch_id}")


@router.get("/patches/{patch_id}/garish.csv", dependencies=[Depends(require_admin)])
def export_outcomes(patch_id: int, session: Session = Depends(get_session)):
    patch = _get_patch(session, patch_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "base_type"])
    for o in patch.garish_outcomes:
        w.writerow([o.name, o.base_type])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="garish-{patch.name}.csv"'},
    )


@router.post("/patches/{patch_id}/garish.csv", dependencies=[Depends(require_admin)])
async def import_outcomes(patch_id: int, file: UploadFile, session: Session = Depends(get_session)):
    """Replace the patch's outcome list with the uploaded CSV (columns: name, base_type)."""
    patch = _get_patch(session, patch_id)
    text = (await file.read()).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "name" not in rows[0]:
        raise HTTPException(400, "CSV needs a header row with a 'name' column (and optionally 'base_type')")
    seen, outcomes = set(), []
    for r in rows:
        n = (r.get("name") or "").strip()
        if n and n not in seen:
            seen.add(n)
            outcomes.append(GarishOutcome(name=n, base_type=(r.get("base_type") or "").strip()))
    patch.garish_outcomes.clear()
    session.flush()
    patch.garish_outcomes.extend(outcomes)
    session.commit()
    return _back(f"/admin/patches/{patch_id}")
