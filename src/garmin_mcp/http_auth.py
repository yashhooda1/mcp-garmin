"""Bearer-token gate for the HTTP transports.

Wraps the FastMCP ASGI app so every HTTP request must present
`Authorization: Bearer <MCP_AUTH_TOKEN>`. Without it the server returns 401.
Lifespan/websocket scopes pass through untouched so the MCP session manager
still starts normally.

Generate a token with:  openssl rand -hex 32
"""
from __future__ import annotations

import hmac
import logging

logger = logging.getLogger("garmin_mcp.http_auth")


class BearerAuthMiddleware:
    """Minimal constant-time bearer check as a pure ASGI wrapper."""

    def __init__(self, app, token: str, oauth=None):
        self.app = app
        self._expected = f"Bearer {token}"
        self._oauth = oauth
        self._challenge = (
            f'Bearer resource_metadata="{oauth.base}/.well-known/oauth-protected-resource"'.encode()
            if oauth else b"Bearer"
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"authorization", b"").decode()
        valid_static = bool(provided and hmac.compare_digest(provided, self._expected))
        valid_oauth = bool(self._oauth and provided[:7].lower() == "bearer " and
                           self._oauth.verify(provided[7:].strip()))
        if not (valid_static or valid_oauth):
            await self._reject(send)
            return
        await self.app(scope, receive, send)

    async def _reject(self, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json"),
                        (b"www-authenticate", self._challenge)],
        })
        await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})


def build_app(mcp, transport: str, host: str, token: str | None):
    """Build the HTTP app, optionally adding OAuth, without changing stdio clients."""
    app = (mcp.streamable_http_app() if transport == "streamable-http"
           else mcp.sse_app())

    # A writable Garmin account must never be exposed without an access gate.
    if not token and host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Set MCP_AUTH_TOKEN before exposing Garmin MCP over HTTP")

    if token:
        from .oauth import OAuthProvider, OAuthRoutes

        oauth = OAuthProvider.from_env(token)
        app = BearerAuthMiddleware(app, token, oauth=oauth)
        if oauth:
            app = OAuthRoutes(app, oauth)
        logger.info("HTTP transport secured with bearer token%s.",
                    " and OAuth" if oauth else "")
    else:
        logger.warning(
            "MCP_AUTH_TOKEN not set: local-only HTTP server is unauthenticated."
        )
    return app


def serve_http(mcp, transport: str, host: str, port: int, token: str | None) -> None:
    """Build the gated FastMCP HTTP app and serve it with uvicorn."""
    import uvicorn

    uvicorn.run(build_app(mcp, transport, host, token), host=host, port=port)
