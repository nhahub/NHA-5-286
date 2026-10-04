"""
Purpose: Safety-check a resolved URL before any browser call is made.
Owner: @Shema
Reads: target_url, ALLOW_HTTP config
Writes: N/A (returns validation result; caller sets terminal_status to BLOCKED on failure)
Must not: infer a missing requirement, accept a blocked URL, substitute a default site
"""

# def is_safe_url(url: str, allow_http: bool = False) -> tuple[bool, str]:
#     -> Checks: scheme is https (unless allow_http), host is not localhost/loopback,
#        host is not in private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x)
#     -> Returns (True, "") or (False, reason_string)

# def is_private_ip(host: str) -> bool:
#     -> Resolves host to IP; returns True if it falls in any SSRF-blocked range

# def check_after_redirect(final_url: str, allow_http: bool = False) -> tuple[bool, str]:
#     -> Re-runs is_safe_url on the post-redirect URL to prevent open-redirect SSRF