"""Read-only production guard for APEX's paused commercial checkout.

Invoke from the existing authorized hourly operator when checking live evidence.
No scheduling, submissions, authentication, purchases, or state changes occur.
The script can fail for network restrictions: such a failure is NOT success.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

LEGACY = "https://ai-revenue-agent-seven.vercel.app"
CURRENT = "https://apex-content-worker-production.up.railway.app"
MAX_RESPONSE_BYTES = 256 * 1024
LEGACY_PATHS = (
    "/",
    "/offer.html",
    "/privacy",
    "/offer.html?setup=https%3A%2F%2Fexample.invalid%2Fbuy&utm_source=read-only-audit",
)


@dataclass(frozen=True)
class Result:
    status: int
    location: str = ""
    body: str = ""


class AuditFailure(Exception):
    """Safety requirement was not verified."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_read_only(url: str) -> Result:
    """GET a fixed public URL, never follow redirects or transmit credentials."""
    allowed = (urlsplit(LEGACY).netloc, urlsplit(CURRENT).netloc)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in allowed or parsed.username or parsed.password:
        raise AuditFailure("destination_not_allowed")
    request = Request(url, headers={"User-Agent": "APEX-read-only-offer-audit/1.0", "Accept": "text/html"})
    opener = build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=8)
    except HTTPError as error:
        response = error  # HTTP 307 is returned here by the NoRedirect handler.
    with response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AuditFailure("response_too_large")
        return Result(int(response.status), response.headers.get("Location", ""), raw.decode("utf-8", "replace"))


def expected_target(path: str) -> str:
    return urljoin(CURRENT + "/", path.lstrip("/"))


def verify_redirect(result: Result, source_url: str, path: str) -> None:
    if result.status != 307:
        raise AuditFailure(f"legacy_not_307: {path}, status={result.status}")
    if not result.location:
        raise AuditFailure(f"missing_location: {path}")
    # The exact scheme, host, path and query must match the reviewed target.
    actual = urljoin(source_url, result.location)
    if actual != expected_target(path):
        raise AuditFailure(f"unexpected_redirect_destination: {path}")


def verify_offer(result: Result, path: str) -> None:
    if result.status != 200:
        raise AuditFailure(f"railway_not_200: {path}, status={result.status}")
    page = result.body.lower()
    if "online checkout is paused" not in page or "does not currently accept payments" not in page:
        raise AuditFailure(f"missing_checkout_pause: {path}")
    if "buy.stripe.com" in page or "checkout.stripe.com" in page:
        raise AuditFailure(f"stripe_checkout_visible: {path}")
    if "params.get('setup')" in page or "params.get('managed')" in page:
        raise AuditFailure(f"query_checkout_override: {path}")
    if 'name="contact_consent"' not in page or 'name="privacy_acknowledged"' not in page:
        raise AuditFailure(f"missing_consent_controls: {path}")


def audit(fetch: Callable[[str], Result] = get_read_only) -> dict[str, object]:
    for path in LEGACY_PATHS:
        source = LEGACY + path
        verify_redirect(fetch(source), source, path)
    for path in ("/", "/offer.html"):
        verify_offer(fetch(CURRENT + path), path)
    return {
        "result": "passed",
        "legacy_redirects_checked": len(LEGACY_PATHS),
        "railway_offer_pages_checked": 2,
        "collection_ready": False,  # This audit never checks merchant eligibility or settlement.
        "revenue_verified": False,
    }


def main() -> int:
    try:
        print(json.dumps(audit(), sort_keys=True))
        return 0
    except (AuditFailure, OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"result": "unverified", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
