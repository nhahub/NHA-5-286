"""
Purpose: The structured outcome of the Preflight check that runs before any LLM-dependent step.
Reads: nothing. Writes: nothing. Holds only values that are safe to show or store (no credentials, no page text).
Must not: contain logic, call the network, or carry a secret.
"""
from __future__ import annotations

from dataclasses import dataclass

PASS = "PASS"
FAILED = "FAILED"
INCONCLUSIVE = "INCONCLUSIVE"

# url_status
REACHABLE = "reachable"
UNREACHABLE = "unreachable"
NOT_CHECKED = "not_checked"

# auth_status
AUTH_NOT_REQUIRED = "not_required"
AUTH_SKIPPED = "skipped"
AUTH_OK = "authenticated"
AUTH_MISSING = "credentials_missing"
AUTH_REJECTED = "credentials_rejected"
AUTH_UNKNOWN = "inconclusive"


@dataclass(frozen=True)
class PreflightResult:
    status: str
    url_status: str
    auth_status: str
    message: str                          # safe, user-facing, already redacted
    error_category: str | None = None
    http_status: int | None = None
    auth_type: str = "username_password"
    auth_required: bool = False           # the site asked for a login and the login worked
    auth_skipped: bool = False            # the user chose not to validate authentication
    duration_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.status == PASS

    def public(self) -> dict:
        return {
            "status": self.status, "url_status": self.url_status, "auth_status": self.auth_status,
            "auth_type": self.auth_type, "http_status": self.http_status, "error_category": self.error_category,
            "message": self.message, "duration_ms": self.duration_ms,
        }

    def markdown(self) -> str:
        icon = {PASS: "✅", FAILED: "⛔", INCONCLUSIVE: "⚠️"}.get(self.status, "")
        lines = [f"### {icon} Preflight {self.status}", self.message, ""]
        lines.append(f"- Website: **{self.url_status.replace('_', ' ')}**"
                     + (f" (HTTP {self.http_status})" if self.http_status else ""))
        lines.append(f"- Authentication: **{self.auth_status.replace('_', ' ')}**")
        lines.append(f"- Checked in {self.duration_ms / 1000:.1f}s. No AI model was called.")
        if self.status != PASS:
            lines.append("\nCorrect the URL or credentials and press **Start Testing** to check again.")
        return "\n".join(lines)
