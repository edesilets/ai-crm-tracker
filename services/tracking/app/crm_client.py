"""Talks to the CRM service over HTTP."""

import os

import httpx

CRM_URL = os.environ.get("CRM_URL", "http://crm:8000").rstrip("/")


class CRMUnavailable(Exception):
    pass


def get_quote(quote_id: int) -> dict | None:
    """Return the quote as JSON, or None if the CRM says it doesn't exist."""
    try:
        resp = httpx.get(f"{CRM_URL}/quotes/{quote_id}", timeout=5)
    except httpx.HTTPError as exc:
        raise CRMUnavailable(f"Could not reach CRM: {exc}") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise CRMUnavailable(f"CRM returned HTTP {resp.status_code}")
    return resp.json()
