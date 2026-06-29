"""Garmin Connect authentication via garth SSO, with cached long-lived tokens.

Flow:
  1. First time, run `garmin-mcp-auth` (see cli.py). It logs in with your
     email/password (+ MFA if enabled) and writes tokens to GARMINTOKENS.
  2. After that, the server resumes from the cached tokens with no credentials
     in its environment.

SECURITY: the cached tokens are long-lived (~1 year) and grant full account
access. Treat GARMINTOKENS like a production secret. This uses Garmin's
unofficial SSO (garth); there is no individual official API.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Callable

from garminconnect import Garmin

DEFAULT_TOKENSTORE = os.path.expanduser("~/.garminconnect")


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS", DEFAULT_TOKENSTORE)


def login_interactive(mfa_prompt: Callable[[], str] = lambda: input("MFA code: ")) -> Garmin:
    """Full interactive login; persists tokens. Used by the auth CLI."""
    email = os.environ.get("GARMIN_EMAIL") or input("Garmin email: ")
    password = os.environ.get("GARMIN_PASSWORD") or _getpass()
    client = Garmin(email=email, password=password, prompt_mfa=mfa_prompt)
    client.login()
    store = tokenstore()
    Path(store).mkdir(parents=True, exist_ok=True)
    client.garth.dump(store)
    return client


def _getpass() -> str:
    import getpass
    return getpass.getpass("Garmin password: ")


@lru_cache(maxsize=1)
def get_client() -> Garmin:
    """Return an authenticated client, cached for the process.

    Resumes from cached tokens; falls back to credential login if env vars are
    present (non-interactive — MFA will fail here, so prefer the auth CLI).
    """
    store = tokenstore()
    client = Garmin()
    try:
        client.login(store)
        return client
    except Exception:
        email = os.environ.get("GARMIN_EMAIL")
        password = os.environ.get("GARMIN_PASSWORD")
        if not (email and password):
            raise RuntimeError(
                "No cached Garmin tokens and no GARMIN_EMAIL/GARMIN_PASSWORD set. "
                "Run `garmin-mcp-auth` once to authenticate."
            )
        client = Garmin(email=email, password=password)
        client.login()
        Path(store).mkdir(parents=True, exist_ok=True)
        client.garth.dump(store)
        return client


def reset_client_cache() -> None:
    get_client.cache_clear()
