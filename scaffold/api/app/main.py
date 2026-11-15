import os
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from app.rejection import rejected

router = APIRouter()


@router.get("/api/health")
def health():
    return {"status": "ok"}


async def invalid_request(request: Request, _exc: RequestValidationError):
    return rejected(request, "invalid_request")  # the framework's default 422 body is never sent


# --- SR-004 security headers ---------------------------------------------------
# Fixed values; nothing from the request is ever copied into a header.
COMMON_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"referrer-policy", b"no-referrer"),
]
COOP = (b"cross-origin-opener-policy", b"same-origin")
CSP_NAME = b"content-security-policy"
# Replaced on every response, in any letter case (set, not append).
OWNED = {name for name, _ in COMMON_HEADERS} | {CSP_NAME, COOP[0], b"content-type"}

# The app's own types win over the runtime MIME table. Only for 200/206 files outside /api/.
CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
}
TEXT_TYPES = {"application/json", "application/javascript", "image/svg+xml"}


# Fixed CSP for HTML responses (SR-004). Widen a source only through a change that specifies it.
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
)


def suffix(path: str) -> str:
    return ".html" if path.endswith("/") else PurePosixPath(path).suffix.lower()


def secure_headers(status: int, path: str, raw: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """The final header list of a response: SR-004 headers set once, exact Content-Type."""
    ctype = next((v.decode("latin-1") for k, v in raw if k.lower() == b"content-type"), None)
    length = next((v for k, v in raw if k.lower() == b"content-length"), None)
    if status in (204, 304) or length == b"0":
        ctype = None  # no body, no Content-Type
    elif ctype is not None:
        if status in (200, 206) and not path.startswith("/api/") and not ctype.startswith("multipart/"):
            ctype = CONTENT_TYPES.get(suffix(path), ctype)  # the path only selects a fixed entry
        base = ctype.split(";")[0].strip().lower()
        if base.startswith("text/") or base in TEXT_TYPES:
            ctype = f"{base}; charset=utf-8"
    headers = [(k, v) for k, v in raw if k.lower() not in OWNED]
    if ctype is not None:
        headers.append((b"content-type", ctype.encode("latin-1")))
    headers += COMMON_HEADERS
    html = ctype is not None and ctype.startswith("text/html")
    if html or (status == 304 and suffix(path) == ".html"):
        headers += [(CSP_NAME, CSP.encode("latin-1")), COOP]
    return headers


def security_headers(app):
    """Outermost pure ASGI wrapper: sees every response, including the 500 of ServerErrorMiddleware."""

    async def wrapped(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        path = scope["path"]

        async def send_secure(message):
            if message["type"] == "http.response.start":
                headers = secure_headers(message["status"], path, list(message.get("headers", [])))
                message = {**message, "headers": headers}
            await send(message)

        await app(scope, receive, send_secure)

    return wrapped


def build(web_dir: Path):
    api = FastAPI(title="@@NAME@@", docs_url=None, redoc_url=None, openapi_url=None)
    api.include_router(router)
    api.add_exception_handler(RequestValidationError, invalid_request)
    if web_dir.is_dir():
        api.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return security_headers(api)


# The built web app (web/dist) is bundled next to the code in Lambda; absent in tests and the k8s image.
WEB_DIR = Path(os.environ.get("WEB_DIR", Path(__file__).parent.parent / "web"))
app = build(WEB_DIR)
handler = Mangum(app, lifespan="off")
