"""Starting point of @@NAME@@: health route, SR-004 headers on every response, 422 rejection without the
framework body. Later changes add their own named tests next to these."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

COMMON = {
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "no-referrer",
}
WEB = Path(__file__).resolve().parents[2] / "web"


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>@@TITLE@@</title>\n")
    return TestClient(main.build(tmp_path), raise_server_exceptions=False)


def test_health_ok(client):
    r = client.get("/api/health")
    assert (r.status_code, r.json()) == (200, {"status": "ok"})


@pytest.mark.parametrize(
    ("path", "status", "html"), [("/", 200, True), ("/api/health", 200, False), ("/nope", 404, False)]
)
def test_security_headers_on_every_response(client, path, status, html):
    r = client.get(path)
    assert r.status_code == status
    for name, value in COMMON.items():
        assert r.headers.get_list(name) == [value], name
    assert (r.headers.get("content-security-policy") == main.CSP) is html
    assert not [k for k in r.headers if k.lower().startswith("access-control-")]


def test_csp_has_no_unsafe_or_wildcard_sources():
    for bad in ("unsafe-inline", "unsafe-eval", "*", "data:", "blob:", "http:"):
        assert bad not in main.CSP, bad


def test_validation_error_is_fixed_422(capsys):
    app = main.FastAPI()
    app.add_exception_handler(main.RequestValidationError, main.invalid_request)

    @app.get("/api/n/{n}")
    def n(n: int):
        return {"n": n}

    r = TestClient(app).get("/api/n/x")
    assert r.status_code == 422 and set(r.json()) == {"error", "request_id"}
    assert r.json()["error"] == "invalid_input"
    event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert event["event"] == "input.rejected" and event["service"] == "@@NAME@@"


def test_page_has_no_inline_code():
    files = [WEB / "index.html", *(p for p in (WEB / "src").rglob("*") if p.is_file())]
    for f in files:
        text = f.read_text()
        for pattern in (r"<style\b", r"\son[a-z]+\s*=", r"innerHTML", r"\beval\s*\(", r"https?://"):
            assert not re.search(pattern, text, re.IGNORECASE), f"{f.name}: {pattern}"
