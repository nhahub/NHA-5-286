"""
Purpose: Step 1 of Preflight: is the website reachable at all? DNS, connection, TLS, timeout and HTTP status.
Reads: the URL. Writes: nothing.
Must not: use an LLM, send credentials, or treat an HTTP 200 as proof of anything about authentication.
"""
from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass

import httpx

TIMEOUT_SECONDS = 15.0
USER_AGENT = "Mozilla/5.0 (compatible; BuglePreflight/1.0)"


@dataclass(frozen=True)
class AccessResult:
    ok: bool                        # the server answered with something a browser can open
    http_status: int | None = None
    category: str | None = None     # dns | ssl | timeout | refused | connection | redirect_loop | invalid_url |
                                    # not_found | server_error | http_error | unauthorized | forbidden
    message: str = ""


def _cause_chain(exc: BaseException):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def _classify_connect_error(exc: httpx.ConnectError) -> tuple[str, str]:
    for err in _cause_chain(exc):
        if isinstance(err, socket.gaierror):
            return "dns", "The website's address could not be found (DNS). Check the spelling of the URL."
        if isinstance(err, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(err):
            return "ssl", "The website's security certificate is not valid (SSL). The connection was not trusted."
        if isinstance(err, ConnectionRefusedError):
            return "refused", "The website refused the connection. It may be down or the port may be wrong."
    return "connection", "Could not connect to the website. Check the URL and your network connection."


def check_access(url: str, timeout: float = TIMEOUT_SECONDS) -> AccessResult:
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url)
    except httpx.TimeoutException:
        return AccessResult(False, None, "timeout", f"The website did not answer within {int(timeout)} seconds.")
    except httpx.ConnectError as exc:
        category, message = _classify_connect_error(exc)
        return AccessResult(False, None, category, message)
    except httpx.TooManyRedirects:
        return AccessResult(False, None, "redirect_loop", "The website keeps redirecting and never loads.")
    except (httpx.InvalidURL, httpx.UnsupportedProtocol):
        return AccessResult(False, None, "invalid_url", "The URL is not valid. Use a full address such as https://example.com.")
    except httpx.HTTPError:
        return AccessResult(False, None, "connection", "The connection to the website failed.")

    code = response.status_code
    if code in (401,):
        return AccessResult(True, code, "unauthorized", "The website answered HTTP 401: it requires authentication.")
    if code == 403:
        return AccessResult(True, code, "forbidden", "The website answered HTTP 403 (access refused).")
    if code in (404, 410):
        return AccessResult(False, code, "not_found", f"The page was not found (HTTP {code}). Check the URL.")
    if code >= 500:
        return AccessResult(False, code, "server_error", f"The website reported a server error (HTTP {code}).")
    if code >= 400:
        return AccessResult(False, code, "http_error", f"The website refused the request (HTTP {code}).")
    return AccessResult(True, code, None, "The website is reachable.")
