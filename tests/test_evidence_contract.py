"""
Purpose: Contract test between support/evidence.ts (P2) and the code that reads the evidence (P3, P4, report).
         It runs REAL Playwright (Chromium) on tiny pages built in memory, so it needs no internet.
Checks: a passing test attaches nothing; a failing test attaches console.json, network.json and
        final-url.txt with the agreed shapes; query strings and fragments never reach the attachments.
Marked integration: it needs Node and Playwright, like the tsc / playwright --list tests.
"""
from __future__ import annotations

import base64
import json
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from validation import validator

pytestmark = pytest.mark.integration

CONTRACT_NAMES = {"console.json", "network.json", "final-url.txt"}

SPECS = {
    "s1-passes.spec.ts": """import { test, expect } from '@support/evidence';

test('passes', async ({ page }) => {
  await page.setContent('<button>Go</button>');
  await expect(page.getByRole('button', { name: 'Go' })).toBeVisible();
});
""",
    "s2-fails.spec.ts": """import { test } from '@support/evidence';

test('fails on purpose', async ({ page }) => {
  await page.setContent('<script>console.error("boom")</script><button>Go</button>');
  throw new Error('failed on purpose');
});
""",
    "s3-query.spec.ts": """import { test } from '@support/evidence';

test('http error with a secret in the query string', async ({ page }) => {
  await page.route('https://example.test/**', (route) =>
    route.fulfill({ status: 404, contentType: 'text/html', body: '<p>gone</p>' }),
  );
  await page.goto('https://example.test/missing?token=secret#frag');
  throw new Error('failed on purpose');
});
""",
}


def _walk_specs(suite: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield from suite.get("specs", [])
    for child in suite.get("suites", []):
        yield from _walk_specs(child)


def attachments_by_spec(results_path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Playwright JSON report -> {spec file: {attachment name: {"contentType", "text"}}}.
    Attachments added with a body are base64 in the report; screenshot and trace have a path instead."""
    data = json.loads(results_path.read_text(encoding="utf-8"))
    found: dict[str, dict[str, dict[str, Any]]] = {}
    for suite in data.get("suites", []):
        for spec in _walk_specs(suite):
            files = found.setdefault(Path(spec["file"]).name, {})
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    for att in result.get("attachments", []):
                        body = att.get("body")
                        files[att["name"]] = {
                            "contentType": att.get("contentType"),
                            "text": base64.b64decode(body).decode("utf-8") if body else None,
                        }
    return found


@pytest.fixture(scope="module")
def evidence_run() -> Iterator[dict[str, dict[str, dict[str, Any]]]]:
    run_dir = validator.PROJECT_ROOT / "runs" / "_pytest" / f"evidence-{uuid.uuid4().hex}"
    tests_dir = run_dir / "tests"
    tests_dir.mkdir(parents=True)
    for name, source in SPECS.items():
        (tests_dir / name).write_text(source, encoding="utf-8")
    try:
        # Exit code 1 is expected here: two of the three specs fail on purpose
        validator._run_npx(["playwright", "test"], {"RUN_DIR": str(run_dir)})
        results = run_dir / "results.json"
        assert results.is_file(), "Playwright did not write results.json"
        yield attachments_by_spec(results)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_a_passing_test_attaches_no_evidence(evidence_run: dict) -> None:
    assert not CONTRACT_NAMES & set(evidence_run["s1-passes.spec.ts"])


def test_a_failing_test_attaches_the_three_contract_files(evidence_run: dict) -> None:
    assert CONTRACT_NAMES <= set(evidence_run["s2-fails.spec.ts"])


def test_content_types_match_the_contract(evidence_run: dict) -> None:
    files = evidence_run["s2-fails.spec.ts"]
    assert files["console.json"]["contentType"] == "application/json"
    assert files["network.json"]["contentType"] == "application/json"
    assert files["final-url.txt"]["contentType"] == "text/plain"


def test_console_json_is_a_list_of_type_and_text(evidence_run: dict) -> None:
    entries = json.loads(evidence_run["s2-fails.spec.ts"]["console.json"]["text"])
    assert entries == [{"type": "error", "text": "boom"}]


def test_network_json_is_a_list_even_when_nothing_failed(evidence_run: dict) -> None:
    assert json.loads(evidence_run["s2-fails.spec.ts"]["network.json"]["text"]) == []


def test_final_url_is_plain_text(evidence_run: dict) -> None:
    assert evidence_run["s2-fails.spec.ts"]["final-url.txt"]["text"] == "about:blank"


def test_http_errors_have_the_agreed_fields(evidence_run: dict) -> None:
    entries = json.loads(evidence_run["s3-query.spec.ts"]["network.json"]["text"])
    assert entries == [
        {"kind": "http_error", "status": 404, "method": "GET", "url": "https://example.test/missing", "failure": None}
    ]


def test_query_strings_and_fragments_never_reach_the_attachments(evidence_run: dict) -> None:
    files = evidence_run["s3-query.spec.ts"]
    assert files["final-url.txt"]["text"] == "https://example.test/missing"
    everything = "".join(f["text"] or "" for f in files.values())
    assert "secret" not in everything and "frag" not in everything