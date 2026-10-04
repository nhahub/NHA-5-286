"""
Purpose: Resolve the target URL from the test_request url field or from requirements text.
Owner: @Shema
Reads: test_request
Writes: target_url (with source annotation)
Must not: infer a missing requirement, accept a blocked URL, substitute a default site, or guess when multiple URLs are present
"""

# def resolve_url(test_request: dict) -> tuple[str | None, str]:
#     -> If url field is set: return (url, "field")
#     -> If url field is empty and exactly one URL found in requirements: return (url, "requirements")
#     -> If url field is empty and multiple URLs found: return (None, "BLOCKED: ambiguous target URL")
#     -> If url field is empty and no URL found: return (None, "BLOCKED: no target URL provided")

# def extract_urls_from_text(text: str) -> list[str]:
#     -> regex-extract all http/https URLs from free text; returns deduplicated list