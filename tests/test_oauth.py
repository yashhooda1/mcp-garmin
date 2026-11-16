"""Offline OAuth tests for ChatGPT/OpenAI; never call Garmin or OpenAI."""
import base64
import hashlib
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from garmin_mcp.http_auth import BearerAuthMiddleware, build_app
from garmin_mcp.oauth import OAuthProvider, OAuthRoutes

BASE = "https://garmin.example.com"
CHATGPT = "https://chatgpt.com/connector_platform_oauth_redirect"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()) \
    .rstrip(b"=").decode()


@pytest.fixture
def setup(tmp_path):
    provider = OAuthProvider(BASE, "my-owner-password", tmp_path / "oauth.json")

    async def ok(_request):
        return PlainTextResponse("mcp ok")

    inner = Starlette(routes=[Route("/mcp", ok)])
    app = OAuthRoutes(BearerAuthMiddleware(inner, "static-token", oauth=provider),
                      provider)
    return provider, TestClient(app, follow_redirects=False)


def register(client, redirect=CHATGPT):
    return client.post("/oauth/register", json={
        "client_name": "ChatGPT", "redirect_uris": [redirect],
    })


def params(cid):
    return {
        "client_id": cid, "redirect_uri": CHATGPT, "response_type": "code",
        "code_challenge": CHALLENGE, "code_challenge_method": "S256",
        "state": "state123", "scope": "workouts offline_access",
        "resource": f"{BASE}/mcp",
    }


def authorize(client, cid, password="my-owner-password"):
    r = client.post("/oauth/authorize", data={**params(cid), "password": password})
    return r


def code_from_response(r):
    return parse_qs(urlparse(r.headers["location"]).query)["code"][0]


def test_metadata_registration_and_login_page(setup):
    _, c = setup
    resource = c.get("/.well-known/oauth-protected-resource/mcp")
    assert resource.status_code == 200
    assert resource.json()["resource"] == f"{BASE}/mcp"
    md = c.get("/.well-known/oauth-authorization-server").json()
    assert "offline_access" in md["scopes_supported"]
    assert md["code_challenge_methods_supported"] == ["S256"]
    assert md["grant_types_supported"] == ["authorization_code", "refresh_token"]

    reg = register(c)
    assert reg.status_code == 201
    page = c.get("/oauth/authorize", params=params(reg.json()["client_id"]))
    assert page.status_code == 200
    assert "ChatGPT" in page.text
    assert page.headers["x-frame-options"] == "DENY"
    assert c.get("/mcp").status_code == 401
    assert "resource_metadata=" in c.get("/mcp").headers["www-authenticate"]


def test_chatgpt_oauth_and_refresh_rotation(setup):
    provider, c = setup
    cid = register(c).json()["client_id"]
    authorization = authorize(c, cid)
    assert authorization.status_code == 302
    assert parse_qs(urlparse(authorization.headers["location"]).query)["state"] == [
        "state123"
    ]
    code = code_from_response(authorization)
    values = {
        "grant_type": "authorization_code", "client_id": cid,
        "code": code, "redirect_uri": CHATGPT, "code_verifier": VERIFIER,
    }
    token_response = c.post("/oauth/token", data=values)
    assert token_response.status_code == 200
    token = token_response.json()
    assert token["refresh_token"] and provider.verify(token["access_token"])
    assert c.get("/mcp", headers={
        "Authorization": f"Bearer {token['access_token']}"
    }).status_code == 200
    assert c.post("/oauth/token", data=values).status_code == 400

    refresh = {"grant_type": "refresh_token", "client_id": cid,
               "refresh_token": token["refresh_token"]}
    newer = c.post("/oauth/token", data=refresh)
    assert newer.status_code == 200
    assert newer.json()["refresh_token"] != token["refresh_token"]
    assert c.post("/oauth/token", data=refresh).status_code == 400
    assert c.get("/mcp", headers={
        "Authorization": "Bearer static-token"
    }).status_code == 200

    persisted = provider.path.read_text()
    assert token["access_token"] not in persisted
    assert token["refresh_token"] not in persisted


def test_invalid_redirect_and_missing_pkce(setup):
    _, c = setup
    assert register(c, "https://evil.example/return").status_code == 400
    assert register(c, "http://chatgpt.com/return").status_code == 400
    cid = register(c).json()["client_id"]
    assert c.get("/oauth/authorize", params={
        **params(cid), "code_challenge_method": "plain"
    }).status_code == 400
    assert c.get("/oauth/authorize", params={
        **params(cid), "redirect_uri": "https://chatgpt.com/unregistered"
    }).status_code == 400
    assert c.get("/oauth/authorize", params={
        **params(cid), "resource": "https://other.example.com/mcp"
    }).status_code == 400


def test_invalid_pkce_and_password_lockout(setup):
    _, c = setup
    cid = register(c).json()["client_id"]
    code = code_from_response(authorize(c, cid))
    r = c.post("/oauth/token", data={
        "grant_type": "authorization_code", "client_id": cid,
        "code": code, "redirect_uri": CHATGPT, "code_verifier": "not-the-verifier",
    })
    assert r.status_code == 400
    for _ in range(5):
        assert authorize(c, cid, password="wrong").status_code == 401
    assert authorize(c, cid).status_code == 429


def test_non_https_public_url_rejected(tmp_path):
    with pytest.raises(ValueError, match="HTTPS"):
        OAuthProvider("http://example.com", "password", Path(tmp_path) / "state.json")


def test_refuse_public_http_without_token():
    class FakeMCP:
        def streamable_http_app(self):
            return Starlette()

    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN"):
        build_app(FakeMCP(), "streamable-http", "0.0.0.0", None)


def test_host_allowlist_configuration(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://garmin.example.com")
    monkeypatch.setenv("TRANSPORT", "streamable-http")
    from garmin_mcp.server import _transport_security

    security = _transport_security()
    if security is not None:
        assert "garmin.example.com" in security.allowed_hosts
        assert "garmin.example.com:*" in security.allowed_hosts
