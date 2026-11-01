"""
Purpose: Deterministic pre-approval check that a proposed spec fix really addresses the diagnosed failure.
Reads: the failing test's error message and call log, the original and proposed spec, the DOM snapshot text.
Writes: nothing. Returns verdicts and structured rejections; the caller decides what to do with them.
Must not: call an LLM, touch files, apply a patch, or consume a healing attempt (that counter only moves in apply_fix).
"""
from __future__ import annotations

import difflib
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

# ----------------------------------------------------------------------------- failure location
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_FRAME_LINE = re.compile(r"^>\s*(\d+)\s*\|", re.M)          # the "> 14 | await ..." marker of Playwright's code frame
_STACK_LINE = re.compile(r"\.spec\.ts:(\d+):\d+")
_LOCATOR_EXPR = r"(?:getBy\w+|locator|frameLocator|page\.\w+|\$)\(.*"
_LOCATOR_LINE = re.compile(rf"^\s*Locator:\s*(?P<expr>{_LOCATOR_EXPR}?)\s*$", re.M)
_WAITING_FOR = re.compile(rf"^\s*-\s*waiting for\s+(?P<expr>{_LOCATOR_EXPR}?)\s*$", re.M)
_EXPR_TAIL = re.compile(r"\s+(?:to (?:be|have|contain|become)\b.*|resolved to\b.*)$")
_IDENT = re.compile(r"\b[A-Za-z_]\w*\b")

MAX_STATEMENT_LINES = 8


def _norm(text: str) -> str:
    """Compare code ignoring quote style and whitespace differences."""
    return re.sub(r"\s+", "", text.replace('"', "'"))


@dataclass(frozen=True)
class FailureTarget:
    line: int                                   # 1-based line Playwright reports as failing
    line_text: str
    locator: str | None                         # the failing locator expression from the call log, when there is one
    target_lines: frozenset[int]                # lines a fix may legitimately change
    locator_lines: frozenset[int] = frozenset() # the occurrence(s) of the locator that belong to THIS failure
    ambiguous: bool = False                     # several equal candidates and none tied to the failing line
    notes: tuple[str, ...] = field(default_factory=tuple)


def _statement_span(lines: list[str], line: int) -> tuple[int, int]:
    """The failing line plus the lines of the same method chain (lines that begin with a dot)."""
    start = end = line
    while start > 1 and lines[start - 1].lstrip().startswith(".") and line - start < MAX_STATEMENT_LINES:
        start -= 1
    while end < len(lines) and lines[end].lstrip().startswith(".") and end - line < MAX_STATEMENT_LINES:
        end += 1
    return start, end


def _definition_lines(lines: list[str], failing_line: int, locator_norm: str, span: tuple[int, int]) -> set[int]:
    """When the failing line uses a variable (const field = page.getByLabel(...)), the lines that define it."""
    used = set()
    for i in range(span[0], span[1] + 1):
        used.update(_IDENT.findall(lines[i - 1]))
    found: set[int] = set()
    for idx in range(1, span[0]):
        text = lines[idx - 1]
        for name in used:
            if re.search(rf"\b(?:const|let|var)\s+{re.escape(name)}\b", text):
                end = idx
                while end < len(lines) and not lines[end - 1].rstrip().endswith(";") and end - idx < MAX_STATEMENT_LINES:
                    end += 1
                statement = lines[idx - 1:end]
                if locator_norm in _norm("".join(statement)):
                    found.update(range(idx, end + 1))
    return found


def locate_failure(error_message: str | None, spec_code: str) -> FailureTarget | None:
    """Find the failing source line and the failing locator from the error message and call log.
    Returns None when the failing line cannot be identified."""
    message = _ANSI.sub("", error_message or "")
    match = _FRAME_LINE.search(message) or _STACK_LINE.search(message)
    lines = spec_code.splitlines()
    if not match or not (1 <= int(match.group(1)) <= len(lines)):
        return None
    line = int(match.group(1))

    locator = None
    for pattern in (_LOCATOR_LINE, _WAITING_FOR):
        found = pattern.search(message)
        if found:
            locator = _EXPR_TAIL.sub("", found.group("expr")).strip()
            break

    span = _statement_span(lines, line)
    targets = set(range(span[0], span[1] + 1))
    locator_lines: set[int] = set()
    ambiguous = False
    notes: list[str] = []
    if locator:
        wanted = _norm(locator)
        in_statement = {i for i in targets if wanted in _norm(lines[i - 1])}
        if not in_statement and wanted in _norm("".join(lines[span[0] - 1:span[1]])):
            in_statement = set(targets)  # the expression is split across the lines of the statement
        if in_statement:
            locator_lines = in_statement
        else:
            defined = _definition_lines(lines, line, wanted, span)
            occurrences = {i for i, text in enumerate(lines, 1) if wanted in _norm(text)}
            if defined:
                locator_lines, targets = defined, targets | defined
                notes.append("the failing line uses a variable defined on the lines above")
            elif len(occurrences) == 1:
                locator_lines, targets = occurrences, targets | occurrences
            elif len(occurrences) > 1:
                ambiguous = True
                notes.append("the failing locator appears on several lines and none is tied to the failing line")
            else:
                notes.append("the failing locator is built dynamically; only the failing statement is a target")
    return FailureTarget(line, lines[line - 1], locator, frozenset(targets), frozenset(locator_lines), ambiguous, tuple(notes))


# ----------------------------------------------------------------------------- evidence
def snapshot_text(page_snapshot: Any) -> str:
    """All text of a page_snapshot value (a dict such as {"aria": "..."}), or "" when there is none."""
    if isinstance(page_snapshot, str):
        return page_snapshot
    if isinstance(page_snapshot, Mapping):
        return "\n".join(filter(None, (snapshot_text(v) for v in page_snapshot.values())))
    if isinstance(page_snapshot, (list, tuple)):
        return "\n".join(filter(None, (snapshot_text(v) for v in page_snapshot)))
    return ""


_TEXT_LOCATOR = re.compile(r"getBy(?:Label|Placeholder|Text|AltText|Title)\(\s*(?P<q>['\"`])(?P<v>.+?)(?P=q)")
_TEXT_REGEX = re.compile(r"getBy(?:Label|Placeholder|Text|AltText|Title)\(\s*/(?P<p>.+?)/(?P<f>[a-z]*)")
_ROLE_LOCATOR = re.compile(
    r"getByRole\(\s*(?P<q1>['\"`])(?P<role>[\w-]+)(?P=q1)"
    r"(?:\s*,\s*\{[^}]*?\bname\s*:\s*(?:(?P<q2>['\"`])(?P<name>.+?)(?P=q2)|/(?P<rx>.+?)/(?P<rf>[a-z]*)))?")
_UNVERIFIABLE = re.compile(r"\b(?:locator|getByTestId|frameLocator)\(|\$\$?\(|xpath=|//\w")


def _locators_in(text: str) -> tuple[list[tuple], bool]:
    """(supported locators found, whether an unverifiable selector such as CSS/test-id/XPath is present)."""
    found: list[tuple] = []
    remaining = text
    for match in _ROLE_LOCATOR.finditer(text):
        found.append(("role", match["role"], match["name"], match["rx"], match["rf"] or ""))
    for match in _TEXT_LOCATOR.finditer(text):
        found.append(("text", match["v"]))
    for match in _TEXT_REGEX.finditer(text):
        found.append(("regex", match["p"], match["f"]))
    return found, bool(_UNVERIFIABLE.search(remaining))


def _supported_by_dom(locator: tuple, snapshot: str) -> bool:
    flat = re.sub(r"\s+", " ", snapshot).lower()
    kind = locator[0]
    if kind == "text":
        return re.sub(r"\s+", " ", locator[1]).strip().lower() in flat
    if kind == "regex":
        try:
            return re.search(locator[1], snapshot, re.I if "i" in locator[2] else 0) is not None
        except re.error:
            return False
    _, role, name, rx, rflags = locator
    for line in snapshot.splitlines():
        head = re.match(r"\s*-\s+(?P<role>[\w-]+)\b(?P<rest>.*)$", line)
        if not head or head["role"].lower() != role.lower():
            continue
        rest = head["rest"]
        if name is None and rx is None:
            return True
        if name is not None and name.strip().lower() in rest.lower():
            return True
        if rx is not None:
            try:
                if re.search(rx, rest, re.I if "i" in rflags else 0):
                    return True
            except re.error:
                continue
    return False


# ----------------------------------------------------------------------------- patch verdict
_FORCED = re.compile(
    r"\bforce\s*:\s*true\b|\{\s*force\s*\}|\bforce\s*[,}]|\.dispatchEvent\s*\(|\.evaluate(?:Handle)?\s*\(|\$\$?eval\s*\(")


@dataclass(frozen=True)
class PatchVerdict:
    ok: bool
    code: str | None = None
    message: str = ""
    codes: tuple[str, ...] = ()


def _ranges(lines: set[int]) -> str:
    return ", ".join(str(n) for n in sorted(lines))


def check_patch(
    original: str,
    fixed: str,
    *,
    target: FailureTarget,
    subtype: str | None,
    snapshot: str,
    lint_name: str = "spec.spec.ts",
    skip_lint_rules: frozenset[str] = frozenset(),
) -> PatchVerdict:
    """Decide, deterministically and before approval, whether `fixed` addresses the failure described by `target`."""
    old, new = original.splitlines(), fixed.splitlines()
    ops = [op for op in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes() if op[0] != "equal"]
    problems: list[tuple[str, str]] = []
    if not ops:
        return PatchVerdict(False, "no_change", "The proposed file is identical to the original.", ("no_change",))
    if target.ambiguous:
        problems.append(("ambiguous_failure", "The failing locator appears on several lines and none can be tied to the "
                         "failure, so a fix cannot be checked against it."))

    # 1. forced interactions are never a fix
    added = "\n".join("\n".join(new[j1:j2]) for _, _, _, j1, j2 in ops)
    if _FORCED.search(added):
        problems.append(("forced_interaction", "The patch adds a forced interaction (force: true, dispatchEvent or "
                         "evaluate). That hides the problem instead of fixing the locator."))

    # 2. every change must sit on the failing statement (or directly next to it, for additions)
    unrelated: set[int] = set()
    for tag, i1, i2, _, _ in ops:
        if tag == "insert":
            if not ({i1, i1 + 1} & target.target_lines):
                unrelated.add(i1 if i1 else 1)
        else:
            unrelated.update(n for n in range(i1 + 1, i2 + 1) if n not in target.target_lines)
    if unrelated:
        problems.append(("unrelated_change", f"The patch changes line(s) {_ranges(unrelated)}, which are not the failing "
                         f"line {target.line} ({target.line_text.strip()[:80]}). Only the failing statement may change."))

    # 3. the failing statement must not simply be removed
    removed_only = [(i1, i2) for tag, i1, i2, j1, j2 in ops if tag == "delete" and any(n in target.target_lines for n in range(i1 + 1, i2 + 1))]
    if removed_only:
        problems.append(("failing_step_removed", "The patch deletes the failing step instead of fixing it."))

    # 4. selector failures: the failing occurrence must be replaced by a locator the DOM supports
    replacement = "\n".join("\n".join(new[j1:j2]) for tag, i1, i2, j1, j2 in ops
                             if tag == "replace" and any(n in target.target_lines for n in range(i1 + 1, i2 + 1)))
    if subtype == "SELECTOR":
        covered = {n for tag, i1, i2, _, _ in ops if tag == "replace" for n in range(i1 + 1, i2 + 1)}
        if target.locator and target.locator_lines:
            if not target.locator_lines <= covered:
                problems.append(("failing_locator_unchanged", f"The failing locator {target.locator} (line(s) "
                                 f"{_ranges(set(target.locator_lines))}) is still in the file unchanged."))
            elif _norm(target.locator) in _norm(replacement):
                problems.append(("failing_locator_unchanged", f"The replacement still uses the failing locator {target.locator}."))
        elif not (target.target_lines & covered):
            problems.append(("failing_locator_unchanged", "The failing statement was not changed."))
        locators, unverifiable = _locators_in(replacement)
        if not replacement.strip():
            pass  # nothing replaced: already reported above
        elif unverifiable:
            problems.append(("insufficient_evidence", "The new selector is CSS, XPath or a test id. The accessibility "
                             "snapshot cannot confirm it, so it cannot be accepted without DOM evidence."))
        elif not locators:
            problems.append(("no_replacement_locator", "The patch does not replace the failing locator with another locator."))
        else:
            missing = [loc for loc in locators if not _supported_by_dom(loc, snapshot)]
            if missing:
                shown = ", ".join(repr(loc[2] or loc[1]) if loc[0] == "role" else repr(loc[1]) for loc in missing)
                problems.append(("unsupported_by_dom", f"The DOM snapshot does not contain {shown}. A selector must be "
                                 "backed by the observed accessible names, labels or roles."))

    # 5. the existing validator rules (no waitForTimeout, no any, no literal secrets, ...)
    try:
        from validation.validator import lint_source

        for issue in lint_source(fixed, lint_name):
            if issue.rule not in skip_lint_rules:
                problems.append((f"lint:{issue.rule}", f"{issue.message} (line {issue.line or '?'})"))
    except ImportError:  # the validator is optional here; the other checks still apply
        pass

    if not problems:
        return PatchVerdict(True)
    return PatchVerdict(False, problems[0][0], " ".join(m for _, m in problems), tuple(c for c, _ in problems))


# ----------------------------------------------------------------------------- results
def make_rejection(code: str, message: str, *, target: FailureTarget | None, subtype: str | None,
                   codes: tuple[str, ...] = (), attempts: int = 0) -> dict:
    """The structured value stored in state['fix_rejection']. Contains no page text and no credentials."""
    return {
        "code": code,
        "codes": list(codes or (code,)),
        "message": message,
        "failing_line": target.line if target else None,
        "failing_locator": target.locator if target else None,
        "subtype": subtype,
        "attempts": attempts,
    }


def apply_diff_text(patch_diff: str, original: str, spec_filename: str) -> str:
    """The text a unified diff would produce, computed on a temporary copy (the real file is never touched)."""
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / spec_filename
        path.write_bytes(original.encode("utf-8"))
        result = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], input=patch_diff.encode("utf-8"),
                                capture_output=True, cwd=temp_dir, timeout=10, check=False)
        if result.returncode != 0:
            raise ValueError("Patch cannot be applied cleanly: " + result.stderr.decode("utf-8", "replace").strip()[:200])
        return path.read_text(encoding="utf-8")
