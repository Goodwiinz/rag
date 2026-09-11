# Codex handoff: NOUS conversation-to-project test

## Requested result

Continue the Playwright test created for the owner's NOUS demo. Validate the real conversation-to-project workflow, diagnose any failures, and return a focused, reviewable change with reproducible test evidence. The application is at https://goodwiinz.tech and the repository is `Goodwiinz/rag` (base branch `develop`).

This folder is a standalone handoff package. Read the root `AGENTS.md` and `docs/engineering/testing.md` before continuing; read narrower instructions when editing their directories.

## Existing workflow and evidence

The manual walkthrough successfully inspected the indexed paper **Attention Is All You Need**, obtained a source-named chat answer, asked the agent to create a research project and attach that paper, approved both tool actions separately, and verified one document after a full project reload.

The default source ID is `74c232ea-e007-4a73-b8ed-df0f88bae654`. It belongs to the demo account; another account or deployment needs its own indexed copy of the same paper and a matching `NOUS_PAPER_ID`.

The test and authentication helper have passed Playwright test discovery and JavaScript syntax validation. The automated authenticated test has **not been executed**. Do not report the earlier manual walkthrough as a passing automated run.

## Continue here

1. Install the isolated package using the repository-pinned Node 24 and pnpm 10.18.2:

   ```bash
   cd tools/nous-playwright
   pnpm install --ignore-workspace
   pnpm exec playwright install chromium
   pnpm test:list
   ```

2. Obtain an authenticated session through the user's normal login. `pnpm auth` runs a headed browser and saves a private `.auth/nous.json` after the user signs in and confirms in the terminal. A cloud runtime without interactive sign-in can use an authenticated storage-state file supplied through its supported private mechanism by setting `NOUS_AUTH_STATE`. Credentials and sessions were deliberately not transferred. If auth is unavailable, finish static/discovery checks and report that the live run is blocked; do not invent credentials or a passing result.
3. Run `pnpm test:headed` locally, or `pnpm test` in an authenticated headless environment. Configure `NOUS_BASE_URL` and `NOUS_PAPER_ID` together when targeting a different deployment. The run creates a unique project and conversation, retains them for inspection, and records their identifiers in the report. It must not delete the existing source paper.
4. Diagnose any failure using the real rendered UI, API response, and retained trace. Correct demonstrably stale selectors or actual defects while preserving the intended checks. Do not mock AI/API results, remove approval gates, weaken persistence assertions, or add retries merely to get a green run.
5. After the standalone flow works, integrate it into the repository's `tests/e2e/` suite if appropriate under its current conventions. Inspect that suite's setup and configuration first; avoid unintentionally running old seeded login or destructive teardown against the live site. Use the package manager to update a lockfile when integrating dependencies. Keep unrelated application changes out of this handoff.
6. Return the exact command, target environment, pass/fail/blocker status, resource IDs, and locations of the video, screenshots, and any failure trace. Keep authenticated artifacts and session state private. Leave changes reviewable in this PR.

## Acceptance criteria

- A fresh chat receives an assistant answer mentioning self-attention and naming the expected source; echoed user text cannot satisfy it.
- The create-project approval matches the unique requested name and contains no extra action.
- The attachment approval matches the expected document and newly created project. The project exists with the expected name and is empty before attachment approval.
- The real project-documents GET and the UI show exactly one correct document membership after approval and again after reload.
- Final assistant messages reconcile without duplicate rows.
- Video and named screenshots are captured; failures retain a trace. One worker and zero retries avoid automatic duplicate projects.

## Known limits

This is a narrow integration smoke test, not a semantic-faithfulness benchmark or latency evaluation. It checks the citation label and ID, but does not navigate the citation. During the manual session, the separate Search page returned no matches for a sentence query; Chat worked. Investigate those separately only if needed for the requested workflow.

The broader conversation involved job-search materials and a demo video, but this task is the NOUS test handoff. No application submission or personal credentials are included.
