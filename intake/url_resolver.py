"""
Purpose: Resolve the target URL from the test_request url field or from requirements text.
Reads: test_request
Writes: target_url (with source annotation)
Must not: infer a missing requirement, accept a blocked URL, substitute a default site, or guess when multiple URLs are present
"""

from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


def extract_urls_from_text(text: str) -> list[str]:
    """Return all http/https URLs in free text, deduplicated, in order of appearance."""
    seen: list[str] = []
    for match in _URL_RE.findall(text or ""):
        url = match.rstrip(".,;:!?")
        if url not in seen:
            seen.append(url)
    return seen


def resolve_url(test_request: dict) -> tuple[str | None, str]:
    url = (test_request.get("url") or "").strip()
    if url:
        return url, "field"
    found = extract_urls_from_text(str(test_request.get("requirements") or ""))
    if len(found) == 1:
        return found[0], "requirements"
    if len(found) > 1:
        return None, "BLOCKED: ambiguous target URL"
    return None, "BLOCKED: no target URL provided"
