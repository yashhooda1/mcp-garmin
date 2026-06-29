"""Interactive one-time auth: `garmin-mcp-auth`.

Logs in with your Garmin credentials (+ MFA if enabled) and caches long-lived
tokens to GARMINTOKENS (default ~/.garminconnect). Run this once; afterwards the
server starts with no credentials in its environment.
"""
from __future__ import annotations

from .auth import login_interactive, tokenstore


def main() -> None:
    print("Garmin Connect authentication")
    print("Tokens will be written to:", tokenstore())
    try:
        client = login_interactive()
        name = client.get_full_name()
        print(f"\n✓ Authenticated as {name}. Tokens cached (valid ~1 year).")
        print("You can now run the MCP server without credentials in env.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n✗ Login failed: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
