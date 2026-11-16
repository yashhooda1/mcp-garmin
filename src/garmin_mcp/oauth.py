"""Self-hosted OAuth 2.1 for ChatGPT and other remote MCP connectors.

Only enabled when PUBLIC_BASE_URL is set. Existing bearer tokens still work.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

DEFAULT_REDIRECT_HOSTS = (
    "chatgpt.com", "chat.openai.com", "claude.ai", "claude.com",
    "localhost", "127.0.0.1",
)
CODE_TTL = 300
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 24 * 3600
SCOPES = "workouts offline_access"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _s256(value: str) -> str:
    digest = hashlib.sha256(value.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class OAuthError(Exception):
    def __init__(self, error: str, description: str, status: int = 400):
        super().__init__(description)
        self.error, self.description, self.status = error, description, status


class OAuthProvider:
    def __init__(self, base: str, password: str, state_path: Path, allowed_hosts=None):
        parsed = urlparse(base)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
            raise ValueError("PUBLIC_BASE_URL must be a public HTTPS origin")
        if not password:
            raise ValueError("Set OAUTH_OWNER_PASSWORD or MCP_AUTH_TOKEN")
        self.base = base.rstrip("/")
        self.password = password
        self.path = Path(state_path)
        self.allowed_hosts = tuple(allowed_hosts or DEFAULT_REDIRECT_HOSTS)
        self._lock = threading.RLock()
        self._failures = {}

    @classmethod
    def from_env(cls, token: str | None):
        base = os.environ.get("PUBLIC_BASE_URL")
        if not base:
            return None
        if not token:
            raise ValueError("MCP_AUTH_TOKEN is required for OAuth")
        hosts = os.environ.get("OAUTH_ALLOWED_REDIRECT_HOSTS", "")
        allowed = tuple(x.strip().lower() for x in hosts.split(",") if x.strip())
        state_dir = Path(os.environ.get("OAUTH_STATE_DIR") or "~/.garmin-mcp").expanduser()
        return cls(base, os.environ.get("OAUTH_OWNER_PASSWORD") or token,
                   state_dir / "garmin-mcp-oauth.json", allowed or None)

    @property
    def resource(self):
        return f"{self.base}/mcp"

    def resource_metadata(self):
        return {"resource": self.resource, "authorization_servers": [self.base],
                "scopes_supported": SCOPES.split(), "bearer_methods_supported": ["header"]}

    def server_metadata(self):
        return {
            "issuer": self.base,
            "authorization_endpoint": f"{self.base}/oauth/authorize",
            "token_endpoint": f"{self.base}/oauth/token",
            "registration_endpoint": f"{self.base}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
            "scopes_supported": SCOPES.split(),
        }

    def _read(self):
        if not self.path.exists():
            return {"clients": {}, "codes": {}, "access": {}, "refresh": {}}
        return json.loads(self.path.read_text())

    def _save(self, state):
        now = time.time()
        for kind in ("codes", "access", "refresh"):
            state[kind] = {k: v for k, v in state[kind].items() if v["exp"] > now}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-oauth-")
        try:
            with os.fdopen(fd, "w") as output:
                json.dump(state, output)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _redirect_ok(self, uri):
        if not isinstance(uri, str):
            return False
        parsed = urlparse(uri)
        host = (parsed.hostname or "").lower()
        if not host or parsed.fragment or parsed.username or parsed.password:
            return False
        if host not in self.allowed_hosts:
            return False
        if host in ("localhost", "127.0.0.1"):
            return parsed.scheme in ("http", "https")
        return parsed.scheme == "https"

    def register(self, payload):
        redirects = payload.get("redirect_uris")
        if not isinstance(redirects, list) or not redirects or not all(
                self._redirect_ok(uri) for uri in redirects):
            raise OAuthError("invalid_redirect_uri", "Allowed HTTPS redirect_uris required")
        method = payload.get("token_endpoint_auth_method", "none")
        if method not in self.server_metadata()["token_endpoint_auth_methods_supported"]:
            raise OAuthError("invalid_client_metadata", "unsupported client authentication")
        client = {
            "client_id": secrets.token_urlsafe(24), "redirect_uris": redirects,
            "client_name": str(payload.get("client_name") or "MCP client")[:100],
            "token_endpoint_auth_method": method,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"], "client_id_issued_at": int(time.time()),
        }
        saved = dict(client)
        if method != "none":
            client["client_secret"] = secrets.token_urlsafe(32)
            client["client_secret_expires_at"] = 0
            saved["secret_hash"] = _hash(client["client_secret"])
        with self._lock:
            state = self._read()
            if len(state["clients"]) >= 100:
                raise OAuthError("invalid_client_metadata", "client registration limit reached", 429)
            state["clients"][client["client_id"]] = saved
            self._save(state)
        return client

    def check_authorize(self, params):
        client = self._read()["clients"].get(params.get("client_id"))
        if not client or params.get("redirect_uri") not in client["redirect_uris"]:
            raise OAuthError("invalid_request", "unregistered client or redirect URI")
        if params.get("response_type") != "code":
            raise OAuthError("unsupported_response_type", "response_type must be code")
        if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
            raise OAuthError("invalid_request", "PKCE S256 is required")
        if params.get("resource") not in (None, "", self.resource):
            raise OAuthError("invalid_request", "invalid resource")
        return client

    def authorize(self, params, password, ip):
        client = self.check_authorize(params)
        now = time.time()
        with self._lock:
            failures = self._failures.get(ip, [])
            failures = [t for t in failures if now - t < 900]
            if len(failures) >= 5:
                raise OAuthError("access_denied", "Too many attempts; retry in 15 minutes", 429)
            if not hmac.compare_digest(password, self.password):
                failures.append(now)
                self._failures[ip] = failures
                raise OAuthError("access_denied", "Wrong server password", 401)
            self._failures.pop(ip, None)
            code = secrets.token_urlsafe(32)
            state = self._read()
            state["codes"][_hash(code)] = {
                "client_id": client["client_id"], "redirect_uri": params["redirect_uri"],
                "challenge": params["code_challenge"], "exp": now + CODE_TTL,
            }
            self._save(state)
        query = {"code": code}
        if params.get("state"):
            query["state"] = params["state"]
        return params["redirect_uri"] + ("&" if "?" in params["redirect_uri"] else "?") + urlencode(query)

    def token(self, form, basic=None):
        client_id = basic[0] if basic else form.get("client_id", "")
        secret = basic[1] if basic else form.get("client_secret", "")
        with self._lock:
            state = self._read()
            client = state["clients"].get(client_id)
            if not client:
                raise OAuthError("invalid_client", "unknown client", 401)
            if client["token_endpoint_auth_method"] != "none":
                if not secret or not hmac.compare_digest(_hash(secret), client["secret_hash"]):
                    raise OAuthError("invalid_client", "invalid client credentials", 401)
            grant = form.get("grant_type")
            if grant == "authorization_code":
                rec = state["codes"].pop(_hash(form.get("code", "")), None)
                if not rec or rec["exp"] < time.time() or rec["client_id"] != client_id or (
                        rec["redirect_uri"] != form.get("redirect_uri")):
                    raise OAuthError("invalid_grant", "invalid or expired code")
                verifier = form.get("code_verifier", "")
                if not verifier or not hmac.compare_digest(_s256(verifier), rec["challenge"]):
                    self._save(state)
                    raise OAuthError("invalid_grant", "PKCE verification failed")
            elif grant == "refresh_token":
                rec = state["refresh"].pop(_hash(form.get("refresh_token", "")), None)
                if not rec or rec["exp"] < time.time() or rec["client_id"] != client_id:
                    raise OAuthError("invalid_grant", "invalid or expired refresh token")
            else:
                raise OAuthError("unsupported_grant_type", "unsupported grant_type")
            access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            now = time.time()
            state["access"][_hash(access)] = {"client_id": client_id, "exp": now + ACCESS_TTL}
            state["refresh"][_hash(refresh)] = {"client_id": client_id, "exp": now + REFRESH_TTL}
            self._save(state)
        return {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TTL,
                "refresh_token": refresh, "scope": SCOPES}

    def verify(self, access):
        rec = self._read()["access"].get(_hash(access))
        return bool(rec and rec["exp"] > time.time())


class OAuthRoutes:
    """ASGI OAuth endpoints, mounted outside the existing bearer gate."""

    def __init__(self, app, provider):
        self.app, self.provider = app, provider

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope.get("path", ""), scope.get("method", "GET")
        supported = (path.startswith("/.well-known/oauth-protected-resource") or
                     path == "/.well-known/oauth-authorization-server" or
                     path in ("/oauth/register", "/oauth/authorize", "/oauth/token"))
        if not supported:
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        p = self.provider
        try:
            if method == "GET" and path.startswith("/.well-known/oauth-protected-resource"):
                result = JSONResponse(p.resource_metadata())
            elif method == "GET" and path == "/.well-known/oauth-authorization-server":
                result = JSONResponse(p.server_metadata())
            elif method == "POST" and path == "/oauth/register":
                if len(await request.body()) > 65536:
                    raise OAuthError("invalid_request", "request too large", 413)
                result = JSONResponse(p.register(await request.json()), status_code=201)
            elif path == "/oauth/authorize" and method in ("GET", "POST"):
                params = dict(request.query_params) if method == "GET" else {
                    key: values[0] for key, values in parse_qs(
                        (await request.body()).decode()).items()}
                client = p.check_authorize(params)
                if method == "GET":
                    fields = ("client_id", "redirect_uri", "response_type", "state",
                              "code_challenge", "code_challenge_method", "scope", "resource")
                    hidden = "".join(
                        f'<input type="hidden" name="{key}" value="{html.escape(str(params[key]), quote=True)}">'
                        for key in fields if params.get(key))
                    page = ('<!doctype html><html><head><title>Connect Garmin MCP</title></head>'
                            '<body><h1>Connect ' + html.escape(client["client_name"]) +
                            ' to Garmin MCP</h1><p>This app can read your Garmin data and '
                            'modify workouts and training calendar events.</p>'
                            '<form method="post" action="/oauth/authorize">' + hidden +
                            '<label>Server password <input type="password" name="password" required></label>'
                            '<button type="submit">Authorize</button></form></body></html>')
                    result = HTMLResponse(page, headers={"x-frame-options": "DENY"})
                else:
                    ip = scope.get("client", ("unknown",))[0] or "unknown"
                    url = p.authorize(params, params.get("password", ""), ip)
                    result = RedirectResponse(url, status_code=302)
            elif method == "POST" and path == "/oauth/token":
                if len(await request.body()) > 65536:
                    raise OAuthError("invalid_request", "request too large", 413)
                form = {key: values[0] for key, values in parse_qs(
                    (await request.body()).decode()).items()}
                auth = request.headers.get("authorization", "")
                basic = None
                if auth.lower().startswith("basic "):
                    try:
                        decoded = base64.b64decode(auth[6:], validate=True).decode()
                        basic = tuple(decoded.split(":", 1))
                        if len(basic) != 2:
                            raise ValueError()
                    except (ValueError, UnicodeError):
                        raise OAuthError("invalid_client", "malformed basic credentials", 401)
                result = JSONResponse(p.token(form, basic))
            else:
                raise OAuthError("invalid_request", "unsupported method", 405)
        except OAuthError as exc:
            result = JSONResponse({"error": exc.error, "error_description": exc.description},
                                  status_code=exc.status)
        except ValueError:
            result = JSONResponse({"error": "invalid_request"}, status_code=400)
        result.headers["cache-control"] = "no-store"
        await result(scope, receive, send)
