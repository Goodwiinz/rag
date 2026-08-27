# NOUS audit-ledger normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize repository and external audit ledgers into SHA-bound statuses so every historical finding is an unverified lead until fresh evidence proves it at an exact commit.

**Architecture:** ledger.py parses the repository’s Markdown provenance block and finding tables with a strict standard-library parser, never inventing missing provenance. It applies exact-SHA evidence and ancestry callbacks supplied by callers, producing immutable NormalizedFinding records. Preflight and candidate selection consume only this normalized view; they never use raw status prose or historical “fixed/open” words as authority.

**Tech Stack:** Python 3.11+ standard library (dataclasses, pathlib, re, typing, csv-like Markdown parsing) and pytest only in tests/unit/scripts/. Git ancestry and receipt evidence are injected callbacks, so Plan 3 does not spawn git or require Plan 2b.

**Spec:** docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md

## Global Constraints

- Depends on Plan 1’s ReceiptStore/preflight interfaces and Plan 0’s Candidate and validation types; it may run alongside Plan 2b and must not import publish.py or reconcile.py.
- Parse docs/audits/AUDIT_LEDGER_TEMPLATE.md format and external ledger directories passed by path; preserve source path and finding ID in every output.
- Every entry begins as lead. confirmed@SHA is allowed only when provenance names a valid exact SHA and an EvidenceProvider proves a launch_audit.sh-isolated worktree at that SHA or a receipt-bound reproduction at that SHA.
- A missing provenance block, missing sha line, or sha: UNRECORDED demotes every entry to lead (unverified); never infer a SHA from file mtime, current HEAD, line references, PR text, or a filename.
- Valid statuses are lead, confirmed@SHA, refuted@SHA, fixed@PR, and stale. confirmed SHA not ancestral to the fetched origin/develop tip is stale; fixed@PR is retained only when a supplied merge-verification callback confirms that PR.
- Candidate selection admits only confirmed@SHA where SHA equals the fetched origin/develop tip or is an ancestor examined this tick. Leads, stale, refuted, and unverified fixed claims are excluded.
- No free-text stdout, prompts, credentials, or arbitrary ledger prose enters a remote projection. Candidate summaries are clipped/sanitized to the Candidate limits from Plan 0.
- Every task uses a red/green cycle and one scoped commit; no ledger files in docs or home directories are modified by implementation.

## File map and cross-plan interfaces

| Path | Ownership in this plan |
| --- | --- |
| scripts/nous/ledger.py | Provenance/table parser, normalized status model, evidence/ancestry validation, candidate conversion. |
| scripts/nous/preflight.py | Add normalized candidate selection hook and PreflightResult.candidates field while preserving existing probe order and authorization. |
| scripts/nous_run.py | Add read-only candidate selection/status output from normalized ledgers; no raw-ledger shortcut. |
| tests/unit/scripts/test_nous_ledger.py | Parser, provenance, status, SHA evidence, and stale/fixed normalization tests. |
| tests/unit/scripts/test_nous_ledger_selection.py | Preflight/candidate integration and sanitization tests. |
| tests/unit/scripts/test_nous_run_cli.py | Extend CLI tests for normalized candidate output and excluded legacy entries. |

Plan 1 owns receipt evidence production; Plan 3 consumes ReceiptEvidenceIndex.has_exact_sha(path: Path, finding_id: str, sha: str) -> bool. Plan 2a’s GitIO-backed preflight may supply is_ancestor(candidate_sha: str, develop_sha: str) -> bool; until then tests use a deterministic callback. Plan 2b’s merge verifier may supply merge_verified_pr(pr: int) -> bool; absent callback means fixed status is a lead.

### Task 1: Parse provenance and Markdown finding tables strictly

**Files:**
- Create: scripts/nous/ledger.py
- Create: tests/unit/scripts/test_nous_ledger.py

**Interfaces:**
- Produces Provenance(session_id: str, checkout: str, ref: str, sha: str | None, primary_head_at_launch: str | None, dirty_status_at_launch: str | None, launched_at: str | None, isolation: str | None).
- Produces RawFinding(finding_id: str, finding: str, severity: str, classification: str | None, raw_status: str, owner: str | None, pr: int | None, updated: str | None, source_path: Path).
- Produces RawLedger(path: Path, provenance: Provenance | None, findings: tuple[RawFinding, ...], warnings: tuple[str, ...]).
- Produces LedgerParseError(ValueError), parse_provenance(lines: Sequence[str], *, path: Path) -> Provenance | None, parse_findings(lines: Sequence[str], *, path: Path) -> tuple[RawFinding, ...], and parse_ledger(path: Path) -> RawLedger.
- parse_provenance recognizes the exact template keys session_id, checkout, ref, sha, primary_head_at_launch, dirty_status_at_launch, launched_at, isolation. A missing block returns None; sha: UNRECORDED is represented as None with a warning. Unknown columns in a finding table are ignored only when they are not status-bearing; duplicate IDs or malformed Markdown rows raise LedgerParseError.
- parse_ledger accepts a Path to one Markdown file; load_raw_ledgers(paths: Iterable[Path]) -> tuple[RawLedger, ...] accepts files and directories and reads only *.md in sorted order.

- [ ] **Step 1: Write failing parser tests**

Create exact fixtures from docs/audits/AUDIT_LEDGER_TEMPLATE.md and a legacy table:

~~~python
def test_template_provenance_and_finding_table_parse(tmp_path):
    path = tmp_path / "audit.md"
    path.write_text(
        "# Audit — started 2026-08-27\n\n"
        "## Provenance\n"
        "- session_id: s-1\n"
        "- checkout: /tmp/audit/worktree\n"
        "- ref: origin/develop\n"
        "- sha: " + HEAD + "\n"
        "- primary_head_at_launch: " + HEAD + "\n"
        "- dirty_status_at_launch: 0\n"
        "- launched_at: 2026-08-27T04:00:00Z\n"
        "- isolation: launch_audit.sh launch --ref develop --slug s\n\n"
        "| ID | Finding | Sev | Class | Status | Owner | PR | Updated |\n"
        "|----|---------|-----|-------|--------|-------|----|---------|\n"
        "| R1-H1 | broken path | high | confirmed | open | — | — | 08-27 |\n",
        encoding="utf-8",
    )
    ledger = parse_ledger(path)
    assert ledger.provenance.sha == HEAD
    assert ledger.findings[0].finding_id == "R1-H1"


def test_unrecorded_provenance_is_not_invented(tmp_path):
    path = tmp_path / "old.md"
    path.write_text(
        "# Old\n\n| ID | Finding | Sev | Status | Owner | PR | Updated |\n"
        "|----|---------|-----|--------|-------|----|---------|\n"
        "| A1 | old fact | med | fixed | — | #12 | 08-01 |\n",
        encoding="utf-8",
    )
    ledger = parse_ledger(path)
    assert ledger.provenance is None
    assert ledger.findings[0].raw_status == "fixed"
~~~

- [ ] **Step 2: Run parser tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger.py -q -k 'parse or provenance' -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because ledger.py and RawLedger do not exist.

- [ ] **Step 3: Implement strict standard-library parsing**

Read UTF-8 with errors=strict and reject control characters in headers/IDs/status-bearing values. Locate the first table whose header contains ID and Finding; split rows on literal pipe boundaries, trim one optional leading/trailing pipe, and map normalized header names. Accept both the template’s Class column and historical tables without Class; missing class becomes None. Parse PR only as null markers or a positive decimal <= 10**7. Reject duplicate finding IDs within one file and report the path/row number without echoing free-text secrets.

Parse provenance only inside the section beginning with ## Provenance and stop at the next ## heading. Preserve the checkout/ref/isolation strings for evidence checks but do not treat them as evidence. For sha, accept a lowercase 40-hex SHA or record None for missing/UNRECORDED; malformed nonempty SHA raises LedgerParseError. A missing provenance section is not a parse failure—it is the required legacy case and receives warning "missing provenance; all findings are unverified leads".

- [ ] **Step 4: Run parser tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger.py -q -k 'parse or provenance' -p no:cacheprovider --no-cov
~~~

Expected: PASS for template and legacy tables, no invented SHA, duplicate/malformed rejection, external directory sorting, UTF-8/control validation, and warning preservation.

- [ ] **Step 5: Commit the parser**

~~~bash
git add scripts/nous/ledger.py tests/unit/scripts/test_nous_ledger.py
git commit -m "feat(nous): parse provenance-aware audit ledgers"
~~~

### Task 2: Normalize statuses with exact evidence and ancestry

**Files:**
- Modify: scripts/nous/ledger.py
- Modify: tests/unit/scripts/test_nous_ledger.py

**Interfaces:**
- Consumes RawLedger and RawFinding from Task 1; consumes validate_sha, validate_pr, reject_secret_text from Plan 0.
- Produces EvidenceProvider protocol has_exact_sha(path: Path, finding_id: str, sha: str) -> bool and AncestorChecker protocol is_ancestor(candidate_sha: str, develop_sha: str) -> bool.
- Produces MergeVerifier protocol merge_verified_pr(pr: int) -> bool.
- Produces NormalizedFinding(finding_id: str, finding: str, severity: str, classification: str | None, status: str, evidence_sha: str | None, pr: int | None, source_path: Path, evidence: str) and NormalizedLedger(path: Path, findings: tuple[NormalizedFinding, ...], warnings: tuple[str, ...]).
- Produces normalize_ledger(raw: RawLedger, *, develop_sha: str, evidence: EvidenceProvider, ancestors: AncestorChecker, merges: MergeVerifier | None = None) -> NormalizedLedger and normalize_paths(paths: Iterable[Path], *, develop_sha: str, evidence: EvidenceProvider, ancestors: AncestorChecker, merges: MergeVerifier | None = None) -> tuple[NormalizedLedger, ...].
- A status string is never trusted as current merely because it says fixed/open/confirmed. confirmed@SHA is produced only from a valid provenance SHA plus exact evidence.has_exact_sha; if the SHA is not an ancestor of develop_sha, output stale. refuted@SHA uses the same exact-evidence requirement. fixed@PR is produced only when merges.merge_verified_pr(pr) is true; otherwise output lead with evidence "fixed status lacks merge-verified PR".

- [ ] **Step 1: Write failing normalization tests**

~~~python
class Evidence:
    def __init__(self, allowed):
        self.allowed = set(allowed)

    def has_exact_sha(self, path, finding_id, sha):
        return (str(path), finding_id, sha) in self.allowed


class Ancestors:
    def __init__(self, values):
        self.values = set(values)

    def is_ancestor(self, candidate_sha, develop_sha):
        return (candidate_sha, develop_sha) in self.values


class FakeMerges:
    def __init__(self, verified):
        self.verified = set(verified)

    def merge_verified_pr(self, pr):
        return pr in self.verified


def test_missing_provenance_demotes_every_entry():
    raw = parse_ledger(LEGACY_PATH)
    result = normalize_ledger(
        raw, develop_sha=HEAD, evidence=Evidence(set()),
        ancestors=Ancestors(set()), merges=None,
    )
    assert {finding.status for finding in result.findings} == {"lead"}
    assert all(f.evidence == "lead (unverified)" for f in result.findings)


def test_exact_confirmed_sha_and_stale_sha_are_distinct():
    raw = parse_ledger(PINNED_PATH)
    result = normalize_ledger(
        raw, develop_sha=HEAD,
        evidence=Evidence({(str(PINNED_PATH), "R1-H1", HEAD)}),
        ancestors=Ancestors({(HEAD, HEAD)}),
    )
    assert result.findings[0].status == "confirmed@" + HEAD


def test_fixed_requires_merge_verified_pr():
    raw = parse_ledger(FIXED_PATH)
    unverified = normalize_ledger(
        raw, develop_sha=HEAD, evidence=Evidence(set()),
        ancestors=Ancestors(set()), merges=FakeMerges(verified=set()),
    )
    assert unverified.findings[0].status == "lead"
    verified = normalize_ledger(
        raw, develop_sha=HEAD, evidence=Evidence(set()),
        ancestors=Ancestors(set()), merges=FakeMerges(verified={12}),
    )
    assert verified.findings[0].status == "fixed@12"
~~~

- [ ] **Step 2: Run normalization tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger.py -q -k 'normal or exact or stale or fixed' -p no:cacheprovider --no-cov
~~~

Expected: FAIL because normalized status types and evidence callbacks are not defined.

- [ ] **Step 3: Implement deterministic status normalization**

If raw.provenance is None or raw.provenance.sha is None, emit lead for every entry and retain the warning; do not inspect raw status or PR to promote anything. Otherwise validate provenance SHA, parse raw status case-insensitively, and extract a SHA only from a status shaped exactly confirmed@40hex or refuted@40hex. For a raw confirmed/open row in a pinned ledger, use the ledger provenance SHA as the candidate evidence SHA only when EvidenceProvider proves that finding ID at that SHA; this supports template ledgers whose status column says open but the run receipt proves it. If exact evidence is absent, output lead with evidence "no exact evidence at pinned SHA".

For an explicit confirmed@SHA/refuted@SHA raw status, require that embedded SHA to equal the ledger provenance SHA before asking EvidenceProvider; a mismatch is a lead with a deterministic provenance-mismatch warning. For confirmed/refuted, call ancestors.is_ancestor(candidate_sha, develop_sha). A false result changes confirmed@SHA to stale and refuted@SHA to stale; retain evidence_sha so the stale reason is machine-visible. The fetched origin/develop SHA itself is accepted as an ancestor of itself. For fixed, parse PR from raw PR column or fixed@PR status, require MergeVerifier, and output fixed@PR only after callback true. Do not call the callback with an invalid/oversized PR.

- [ ] **Step 4: Run normalization tests and Plan 0–1 tests**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/test_nous_schema.py tests/unit/scripts/test_nous_receipt.py tests/unit/scripts/test_nous_preflight.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for every legacy demotion, exact confirmed/refuted evidence, stale ancestry, merge-verified fixed status, no invented SHA, and all earlier plan tests.

- [ ] **Step 5: Commit normalized status semantics**

~~~bash
git add scripts/nous/ledger.py tests/unit/scripts/test_nous_ledger.py
git commit -m "feat(nous): normalize ledger statuses by exact sha"
~~~

### Task 3: Integrate normalized candidates into preflight and CLI

**Files:**
- Modify: scripts/nous/preflight.py
- Modify: scripts/nous_run.py
- Create: tests/unit/scripts/test_nous_ledger_selection.py
- Modify: tests/unit/scripts/test_nous_run_cli.py

**Interfaces:**
- Consumes normalize_paths, NormalizedLedger, NormalizedFinding, EvidenceProvider, AncestorChecker, MergeVerifier, Candidate, PreflightResult, Authorization, and existing Plan 1 probe order.
- Extends PreflightResult with candidates: tuple[Candidate, ...] = () and ledger_warnings: tuple[str, ...] = () after existing fields; existing callers constructing PreflightResult remain source-compatible through these trailing defaults.
- Produces select_normalized_candidates(ledgers: Sequence[NormalizedLedger], *, develop_sha: str) -> tuple[Candidate, ...]. It admits only status strings beginning confirmed@, with evidence_sha equal develop_sha or an ancestor checked by the supplied normalized ledger result; it orders by source path then finding_id and clips summaries to 200 characters through the Plan 0 validator.
- Produces collect_ledger_candidates(*, paths: Iterable[Path], develop_sha: str, evidence: EvidenceProvider, ancestors: AncestorChecker, merges: MergeVerifier | None = None) -> tuple[tuple[Candidate, ...], tuple[str, ...]].
- Extends run_preflight(*, agent: str, backend: CoordinationBackend | LocalMutex, probes: PreflightProbes, authorization: Authorization, mode: str, ledger_paths: Iterable[Path] = (), evidence: EvidenceProvider | None = None, ancestors: AncestorChecker | None = None, merges: MergeVerifier | None = None) -> PreflightResult. If ledger_paths is empty it preserves candidates=(); if paths are supplied and callbacks are missing, it fails with ValidationError rather than treating raw ledgers as candidates. Preflight remains receipt-free; the later claim command creates the one run ID and local receipt.
- CLI status/list/preflight --json serializes candidates and warnings from normalized data only. claim’s candidate-source/summary is validated but the CLI never auto-claims a lead or stale finding.

- [ ] **Step 1: Write failing candidate-selection tests**

~~~python
def test_only_current_confirmed_findings_become_candidates():
    current = NormalizedFinding(
        finding_id="R1-H1", finding="R1-H1", severity="medium", classification=None,
        status="confirmed@" + HEAD, evidence_sha=HEAD, pr=None,
        source_path=Path("a.md"), evidence="exact receipt evidence",
    )
    lead = NormalizedFinding(
        finding_id="R1-H2", finding="R1-H2", severity="medium", classification=None,
        status="lead", evidence_sha=None, pr=None, source_path=Path("a.md"),
        evidence="lead (unverified)",
    )
    stale = NormalizedFinding(
        finding_id="R1-H3", finding="R1-H3", severity="medium", classification=None,
        status="stale", evidence_sha=OLD_HEAD, pr=None, source_path=Path("b.md"),
        evidence="confirmed SHA is not an ancestor of develop",
    )
    candidates = select_normalized_candidates(
        (NormalizedLedger(Path("a.md"), (current, lead), ()),
         NormalizedLedger(Path("b.md"), (stale,), ())),
        develop_sha=HEAD,
    )
    assert [(item.source, item.summary, item.lead_ref) for item in candidates] == [
        ("audit-ledger", "R1-H1", "a.md#R1-H1")
    ]


def test_preflight_rejects_raw_ledger_without_evidence_callbacks(fake_probe, fake_backend, tmp_path):
    path = tmp_path / "audit.md"
    path.write_text("| ID | Finding | Status |\n|--|--|--|\n| A1 | x | open |\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        run_preflight(
            agent="agent", backend=fake_backend, probes=fake_probe,
            authorization=Authorization.from_names(["coordinate"]), mode="local",
            ledger_paths=(path,),
        )
~~~

- [ ] **Step 2: Run candidate tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger_selection.py tests/unit/scripts/test_nous_run_cli.py -q -k 'candidate or ledger' -p no:cacheprovider --no-cov
~~~

Expected: FAIL because PreflightResult has no normalized candidates and candidate collection is not wired.

- [ ] **Step 3: Implement normalized candidate integration**

After the existing five preflight probe calls and before constructing PreflightResult, call collect_ledger_candidates only for explicitly supplied paths. Use the already fetched base SHA as develop_sha. If no exact evidence/ancestry callback is available, raise ValidationError; do not downgrade this failure to an empty candidate list. Append ledger warnings to the result but do not place warning prose in remote metadata. Keep authorization and no-remote-run behavior unchanged.

Build Candidate(source="audit-ledger", summary=sanitized one-line finding, lead_ref=display path + "#" + finding_id). A path below the repository root uses its repository-relative POSIX form; an explicitly supplied external ledger uses a non-secret basename plus a stable SHA-256 path digest, never its absolute local path. Use only finding IDs, severity, and sanitized one-line text; reject control characters/secret patterns and cap 200 characters. Candidate ordering is deterministic and duplicate IDs from different files retain distinct lead_ref values. The CLI JSON uses a list of objects with source, summary, and lead_ref; human output labels each as a normalized confirmed candidate. No raw status table is printed.

- [ ] **Step 4: Run integration tests and the full isolated script gate**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger_selection.py tests/unit/scripts/test_nous_run_cli.py tests/unit/scripts/test_nous_preflight.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for current-confirmed-only candidate selection, no evidence-callback shortcut, deterministic lead refs, warning reporting, local/remote preflight behavior, stable CLI JSON, and all Plan 0–2b tests present at this phase.

- [ ] **Step 5: Commit candidate integration**

~~~bash
git add scripts/nous/preflight.py scripts/nous_run.py tests/unit/scripts/test_nous_ledger_selection.py tests/unit/scripts/test_nous_run_cli.py
git commit -m "feat(nous): select only sha-verified ledger candidates"
~~~

### Task 4: Freeze legacy-ledger and stdlib security contracts

**Files:**
- Create: tests/unit/scripts/test_nous_ledger_contract.py

**Interfaces:**
- Consumes parse_ledger, normalize_ledger, normalize_paths, collect_ledger_candidates, select_normalized_candidates, NormalizedLedger, NormalizedFinding, and the evidence/ancestry callback protocols.
- Produces contract tests proving missing provenance and sha: UNRECORDED demote every entry, malformed SHA never becomes a candidate, no SHA is inferred from current HEAD or PR, stale status is used when a confirmed SHA is not an ancestor, and fixed@PR requires merge verification.
- Produces a pure-stdlib import test that hides third-party site-packages and imports every module under scripts/nous/, including ledger.py after Plan 2a modules exist.
- Produces AST-based source tests rejecting subprocess imports/calls in ledger.py and preflight.py; GitIO remains the only process boundary. Tests inspect imports and call nodes rather than rejecting harmless documentation strings.

- [ ] **Step 1: Write failing contract tests**

~~~python
import ast


def test_legacy_and_unrecorded_ledgers_are_all_leads(legacy_paths, callbacks):
    ledgers = normalize_paths(
        legacy_paths, develop_sha=HEAD, evidence=callbacks.evidence,
        ancestors=callbacks.ancestors, merges=callbacks.merges,
    )
    assert all(f.status == "lead" for ledger in ledgers for f in ledger.findings)


def test_stale_sha_is_not_current_candidate():
    finding = NormalizedFinding(
        finding_id="A1", finding="A1", severity="medium", classification=None,
        status="confirmed@" + OLD_HEAD, evidence_sha=OLD_HEAD, pr=None,
        source_path=Path("audit.md"), evidence="exact receipt evidence",
    )
    ledger = NormalizedLedger(Path("audit.md"), (finding,), ())
    assert select_normalized_candidates((ledger,), develop_sha=HEAD) == ()


def test_ledger_module_has_no_subprocess_boundary():
    tree = ast.parse(Path("scripts/nous/ledger.py").read_text(encoding="utf-8"))
    assert not any(
        (isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "subprocess")
        for node in ast.walk(tree)
    )
~~~

- [ ] **Step 2: Run contract tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger_contract.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because the contract file and final legacy/security assertions are not present.

- [ ] **Step 3: Implement fail-closed regression guards**

Add explicit tests for every legacy case in the spec: no provenance section, sha absent, sha UNRECORDED, malformed 40-hex, confirmed SHA with no ReceiptEvidenceIndex record, confirmed SHA not ancestral to develop, and fixed PR whose merge callback returns false. Ensure all output status values are from the five-element model and all warnings are deterministic. Keep the normalization layer read-only; it must not rewrite ledger Markdown or update status columns.

- [ ] **Step 4: Run the contract and complete script gate**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_ledger_contract.py tests/unit/scripts/test_nous_ledger.py tests/unit/scripts/test_nous_ledger_selection.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for all legacy demotions, exact evidence, stale classification, fixed merge verification, no subprocess boundary, and every previous script test.

- [ ] **Step 5: Commit the ledger contracts**

~~~bash
git add scripts/nous/ledger.py scripts/nous/preflight.py tests/unit/scripts/test_nous_ledger_contract.py
git commit -m "test(nous): freeze legacy ledger revalidation rules"
~~~

## Plan-level verification and acceptance evidence

Run after all task commits:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
python3 -m compileall -q scripts/nous scripts/nous_run.py
python3 - <<'PY'
from pathlib import Path
import ast
for path in Path("scripts/nous").glob("*.py"):
    if path.name == "gitio.py":
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert not any(
        (isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "subprocess")
        for node in ast.walk(tree)
    )
print("ledger stdlib/source boundary ok")
PY
git diff --check
~~~

Expected: all isolated tests pass, compileall and diff check are silent, and the source-boundary command prints ledger stdlib/source boundary ok. Acceptance evidence is a normalized output in which every missing/unrecorded-provenance entry is lead (unverified), only exact receipt/audit SHA evidence can produce confirmed@SHA or refuted@SHA, non-ancestral confirmations are stale, merge-verified PRs alone produce fixed@PR, and candidate selection excludes every non-current status. Plan 3 may be reviewed and merged alongside Plan 2b; it does not gate the remote cutover.
