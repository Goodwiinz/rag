# Playwright Apt-Source Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unrelated `packages.microsoft.com` outages from breaking Playwright's Ubuntu dependency installation in the E2E job.

**Architecture:** Add a small standard-library Python helper that moves apt source files containing a configured host into an ephemeral quarantine directory. Exercise the helper against real temporary files, then invoke it as root immediately before Playwright runs `install --with-deps chromium`; Ubuntu sources and Playwright's dependency management remain unchanged.

**Tech Stack:** Python 3.11, pytest, GitHub Actions YAML, Playwright, actionlint.

## Global Constraints

- Quarantine only source files whose contents contain `packages.microsoft.com`.
- Preserve every Ubuntu and Google apt source.
- Keep `playwright install --with-deps chromium`; do not hand-maintain Playwright's OS dependency list.
- Use only Python's standard library so the helper works before project dependencies are installed.
- Make no changes to application runtime behavior.

---

### Task 1: Quarantine unrelated Microsoft apt sources

**Files:**
- Add: `backend/tests/unit/ci/test_quarantine_apt_sources.py`
- Add: `scripts/ci/quarantine_apt_sources.py`
- Modify: `.github/workflows/test-pipeline.yml:1142-1153`

**Interfaces:**
- Produces: `quarantine_matching_sources(source_dir: Path, quarantine_dir: Path, host: str) -> list[Path]`
- Consumes: apt source files under `/etc/apt/sources.list.d` and an ephemeral quarantine directory under `/tmp`.

- [x] **Step 1: Write the failing behavioral test**

Create real `.list` and `.sources` files in `tmp_path`, including two that reference `packages.microsoft.com` and one Ubuntu source. Invoke the helper CLI with the temporary source and quarantine directories, then assert that only the two Microsoft files moved with their contents intact.

- [x] **Step 2: Verify the regression test fails for the missing helper**

Run:

```bash
/tmp/pr1386-venv-311/bin/python -m pytest backend/tests/unit/ci/test_quarantine_apt_sources.py -q
```

Expected: the test fails because the subprocess cannot open `scripts/ci/quarantine_apt_sources.py`.

- [x] **Step 3: Implement the minimal helper**

Implement the typed standard-library function and a CLI whose defaults are:

```text
--sources-dir=/etc/apt/sources.list.d
--quarantine-dir=/tmp/playwright-disabled-apt-sources
--host=packages.microsoft.com
```

The helper must sort candidates, ignore directories, create the quarantine directory only when a match exists, move each matching file, and return the original matching paths.

- [x] **Step 4: Verify the focused test passes**

Run the same pytest command and require a zero exit status.

- [x] **Step 5: Wire the helper into E2E**

Immediately before `pnpm --dir tests/e2e exec playwright install --with-deps chromium`, run:

```bash
sudo python3 scripts/ci/quarantine_apt_sources.py
```

Document that the quarantined Microsoft repositories are unrelated to Playwright and that the hosted runner is ephemeral.

- [x] **Step 6: Validate the workflow and surrounding CI contracts**

Run:

```bash
/tmp/pr1386-venv-311/bin/python -m pytest backend/tests/unit/ci/test_quarantine_apt_sources.py backend/tests/unit/ci/test_release_gate.py -q
actionlint .github/workflows/test-pipeline.yml
python3 scripts/docs/check_dir_docs.py
git diff --check
```

- [ ] **Step 7: Publish and verify remotely**

Commit only the helper, regression test, workflow change, and this plan. Push `codex/pr-1386-review-remediation`, then monitor PR #1387 until E2E and Release Gate complete successfully.
