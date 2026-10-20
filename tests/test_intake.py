"""
Purpose: Tests for intake/ package — URL resolution, safety checks, and model resolution.
"""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "fixtures" / "intake_cases.json").read_text(encoding="utf-8"))
URL_SAFETY = CASES["url_safety"]

AGENT_FIELDS = (
    ("planner", "planner_model"),
    ("codegen", "codegen_model"),
    ("analyzer", "healer_model"),       # Healer Model applies to the Failure Analyzer ...
    ("fix_proposal", "healer_model"),   # ... and to the Fix Proposal agent (spec section 6)
)
AGENTS = {agent for agent, _ in AGENT_FIELDS}
COMPARED_KEYS = AGENTS | {"status", "reason"}
PROVIDER_KEY = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
MODEL_FORMAT = re.compile(r"^[a-z0-9_-]+:\S+$")
BLOCKED_NETWORKS = [
    ipaddress.ip_network(n)
    for n in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
              "0.0.0.0/8", "::1/128", "fc00::/7", "fe80::/10")
]


# --------------------------------------------------------------- reference rules
def _parse_ip(host: str):
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if re.fullmatch(r"0x[0-9a-f]+", host, re.I):
        return ipaddress.ip_address(int(host, 16))
    if re.fullmatch(r"0[0-7]+", host):
        return ipaddress.ip_address(int(host, 8))
    if re.fullmatch(r"\d+", host):
        return ipaddress.ip_address(int(host))
    return None


def reference_blocked(url: str, allow_http: bool = False) -> bool:
    try:
        parts = urlsplit(url)
        host, scheme = parts.hostname, parts.scheme.lower()
    except ValueError:
        return True
    if scheme != "https" and not (allow_http and scheme == "http"):
        return True
    if not host or parts.username:
        return True
    ip = _parse_ip(host)
    if ip is not None:
        ip = getattr(ip, "ipv4_mapped", None) or ip
        return any(ip in network for network in BLOCKED_NETWORKS)
    name = host.rstrip(".").lower()
    return name == "localhost" or name.endswith(".localhost")


def extract_urls(text: str) -> list[str]:
    """Matches the stub in intake/url_resolver.py: all http(s) URLs, deduplicated."""
    found = (u.rstrip(".,;:!?)") for u in re.findall(r"https?://[^\s\"'<>]+", text))
    return list(dict.fromkeys(found))


def reference_url_resolution(case: dict) -> dict:
    field = (case["field"] or "").strip()
    if field:
        url, source = field, "field"
    else:
        urls = extract_urls(case["text"])
        if not urls:
            return {"status": "BLOCKED", "reason": "no target URL provided"}
        if len(urls) > 1:
            return {"status": "BLOCKED", "reason": "ambiguous target URL"}
        url, source = urls[0], "requirements"
    if reference_blocked(url):
        return {"status": "BLOCKED", "reason": "unsafe URL"}
    return {"status": "ok", "source": source, "url": url}


def reference_resolution(case: dict) -> dict:
    """Override, then DEFAULT_MODEL; ERROR before any spend if nothing usable (spec section 6)."""
    chosen: dict[str, str] = {}
    for agent, field in AGENT_FIELDS:
        model = (case["request"].get(field) or "").strip() or case["default_model"]
        if not model:
            return {"status": "ERROR", "reason": "no usable model"}
        chosen[agent] = model
    for model in chosen.values():
        if PROVIDER_KEY[model.split(":")[0]] not in case["env_keys_present"]:
            return {"status": "ERROR", "reason": "missing API key"}
    return chosen


# --------------------------------------------------------------------------- tests
def test_ids_are_unique_within_each_list() -> None:
    lists = {
        "url_resolution": CASES["url_resolution"],
        "authorization": CASES["authorization"]["cases"],
        "model_resolution": CASES["model_resolution"],
        **{f"url_safety.{name}": items for name, items in URL_SAFETY.items()},
    }
    for name, items in lists.items():
        ids = [item["id"] for item in items]
        assert len(ids) == len(set(ids)), f"duplicate ids in {name}"


def test_blocked_entries_are_well_formed() -> None:
    codes = set(CASES["reason_codes"])
    for entry in URL_SAFETY["blocked"]:
        assert entry["tier"] in {"spec", "extended"}, entry["id"]
        assert entry["reason_any_of"], entry["id"]
        assert set(entry["reason_any_of"]) <= codes, f"{entry['id']}: unknown reason code"


def test_url_labels_agree_with_an_independent_oracle() -> None:
    wrong = [e["id"] for e in URL_SAFETY["blocked"] if not reference_blocked(e["url"])]
    wrong += [e["id"] for e in URL_SAFETY["allowed"] if reference_blocked(e["url"])]
    wrong += [
        e["id"] for e in URL_SAFETY["http_opt_in"]
        if reference_blocked(e["url"], e["allow_http"]) != (e["expect"] == "blocked")
    ]
    wrong += [
        e["id"] for e in URL_SAFETY["redirect_cases"]
        if reference_blocked(e["start"]) or reference_blocked(e["redirects_to"]) != (e["expect"] == "blocked")
    ]
    wrong += [e["id"] for e in URL_SAFETY["dns_cases"] if not reference_blocked(f"https://{e['resolves_to']}")]
    assert not wrong, f"fixture labels disagree with the reference rules: {wrong}"


def test_url_resolution_cases_agree_with_the_reference_rules() -> None:
    for case in CASES["url_resolution"]:
        got = reference_url_resolution(case)
        for key, want in case["expect"].items():
            if key != "note":
                assert got.get(key) == want, f"{case['id']}: {key} expected {want!r}, reference gives {got.get(key)!r}"


def test_model_resolution_cases_are_consistent() -> None:
    for case in CASES["model_resolution"]:
        assert set(case["request"]) == {"planner_model", "codegen_model", "healer_model"}, case["id"]
        expect = case["expect"]
        if "status" in expect:
            assert expect["status"] == "ERROR" and expect.get("reason"), case["id"]
        else:
            assert set(expect) == AGENTS, f"{case['id']}: expect must name every agent {sorted(AGENTS)}"
            assert all(MODEL_FORMAT.match(m) for m in expect.values()), case["id"]
        if case.get("open_question") or case.get("needs_mock"):
            continue
        got = reference_resolution(case)
        for key, want in expect.items():
            if key in COMPARED_KEYS:
                assert got.get(key) == want, f"{case['id']}: {key} expected {want!r}, reference gives {got.get(key)!r}"


def test_no_literal_secrets_in_the_fixture() -> None:
    def walk(node, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = key.lower()
                if isinstance(value, str) and value and any(w in lowered for w in ("password", "secret", "token")):
                    assert lowered.endswith("_env"), f"literal secret at {path}/{key}"
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(CASES)
