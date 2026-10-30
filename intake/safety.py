"""
Purpose: Safety-check a resolved URL before any browser call is made.
Reads: target_url, ALLOW_HTTP config
Writes: N/A (returns validation result; caller sets terminal_status to BLOCKED on failure)
Must not: infer a missing requirement, accept a blocked URL, substitute a default site
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse


def _allow_http_default() -> bool:
    return os.environ.get("ALLOW_HTTP", "false").strip().lower() == "true"


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def is_private_ip(host: str) -> bool:
    """True when the host is, or resolves to, a loopback/private/link-local address."""
    try:
        return _blocked_ip(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # unresolved here; the browser run reports an unreachable app as BLOCKED
    return any(_blocked_ip(ipaddress.ip_address(info[4][0].split("%")[0])) for info in infos)


def is_safe_url(url: str, allow_http: bool | None = None) -> tuple[bool, str]:
    allow_http = _allow_http_default() if allow_http is None else allow_http
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False, "BLOCKED: target URL must be an http(s) URL"
    if parsed.scheme == "http" and not allow_http:
        return False, "BLOCKED: plain HTTP targets are not allowed (set ALLOW_HTTP=true)"
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost") or is_private_ip(host):
        return False, "BLOCKED: target host is local or in a private network range"
    return True, ""


def check_after_redirect(final_url: str, allow_http: bool | None = None) -> tuple[bool, str]:
    return is_safe_url(final_url, allow_http)
