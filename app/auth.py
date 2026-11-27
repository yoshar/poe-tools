import hmac

from fastapi import HTTPException, Request

from .config import settings


def is_admin(request: Request) -> bool:
    return bool(settings.admin_password) and request.session.get("admin") is True


def check_password(password: str) -> bool:
    if not settings.admin_password:
        return False
    return hmac.compare_digest(password.encode(), settings.admin_password.encode())


class NeedsLogin(Exception):
    pass


def require_admin(request: Request) -> None:
    if not settings.admin_password:
        raise HTTPException(503, "Admin is disabled: set ADMIN_PASSWORD to turn it on.")
    if not is_admin(request):
        raise NeedsLogin()
