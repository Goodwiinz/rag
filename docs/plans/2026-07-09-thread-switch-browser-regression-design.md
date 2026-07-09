# Thread-switch browser regression design

## Goal

Turn the browser-only `/chat` thread-switch crash reproduction into repeatable
release evidence without changing the existing runtime remediation.

## Chosen approach

Add a focused Playwright regression against the repository's CI E2E stack. It
will prepare two distinct chat threads, with one transcript above the
virtualization threshold, alternate the real sidebar controls 24 times at a
45 ms cadence, and assert that the page remains alive and ends on the selected
thread's transcript. The test must fail on a browser `pageerror`.

The existing Vitest coverage remains the fast contract layer: it proves the
MessageByIndex error-boundary behavior and the thread-keyed remount. The new
browser test covers the concurrent scheduler and reconciler path that jsdom
cannot reproduce.

## Release evidence

After automated verification, run the same rapid-switch sequence in the
authenticated dev browser session. Confirm the deployed `dpl_` hash before
testing, record the absence of client-side exceptions, and keep this manual
check outside CI because it requires live credentials and deployment state.

## Constraints

- Preserve the #1096 boundary and #1098 thread-keyed row subtree; do not
  change production rendering behavior to make the test easier.
- Reuse the existing E2E fixture/authentication path and deterministic data
  setup where available.
- Avoid coupling CI to `goodwiinz.tech` or a developer's authenticated session.
