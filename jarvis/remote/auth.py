import secrets

from fastapi import HTTPException, Request, WebSocket

from .. import config


def _valid(token) -> bool:
    return secrets.compare_digest(token or "", config.REMOTE_TOKEN or "")


def require_token(request: Request):
    """FastAPI dependency guarding /api/* routes (except /api/health)."""
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else None
    if not _valid(token):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


async def require_token_ws(websocket: WebSocket) -> bool:
    """Validates the token on a WebSocket connection before it's accepted.
    Browsers can't reliably set custom headers on the WS handshake, so the
    token travels as a query param instead."""
    token = websocket.query_params.get("token")
    if not _valid(token):
        await websocket.close(code=4401)
        return False
    return True
