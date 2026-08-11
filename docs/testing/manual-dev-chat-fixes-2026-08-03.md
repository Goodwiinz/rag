# Manual Dev Test - Chat Thread Fixes

## Scope

- Environment: [NOUS dev](https://dev-app.gen-text.app)
- Change under test: `5786a2c4` - `fix(chat): scope thread-load errors, harden thread-switch/delete paths (#1339)`
- Areas: `/chat` thread loading, URL synchronization, live-stream switching/resume, and single/bulk deletion
- Out of scope: agent answer quality and backend performance

## Deployment gate

Do not start or record results until the Vercel deployment for commit `5786a2c4` is successful.

Snapshot at `2026-08-03T22:54:01Z`:

- Vercel reported `Deployment has completed` for `5786a2c4`.
- Frontend Tests and Lint Frontend passed for the commit.
- The overall Test Pipeline was still running because unrelated backend/unit jobs had not finished.
- The Kubernetes backend image remained `61f7088`; that is expected for this frontend-only change and is not the frontend deployment gate.

## Tester setup

Use a test account with at least three conversations containing visibly different messages. Name them `Thread A`, `Thread B`, and `Thread C` for the test, if possible.

Have Chrome DevTools open on the Network tab with **Preserve log** enabled. Record the browser, viewport, commit, time, and result for each test. Capture a screenshot and the failed request for every failure.

Run the critical tests on desktop first. Repeat the basic switching and delete smoke tests at a mobile viewport after the desktop pass.

## P0 - Streaming thread switch, return, and stop

Purpose: verify that switching away from a live turn does not lose its optimistic messages or leave the resumed stream impossible to stop.

1. Open `Thread A` and note its `?thread=<id>` URL.
2. Submit a prompt that produces a long response, such as: `Research three approaches to evaluating a RAG system, compare their tradeoffs, and give me a recommendation.`
3. As soon as the user prompt and assistant activity appear, click `Thread B`.
4. Confirm `Thread B` shows only its own transcript. It must not show Thread A's prompt, partial answer, typing indicator, or a full-page skeleton over cached messages.
5. Click `Thread A` while the turn is still running.
6. Confirm the submitted user prompt is still visible and the assistant response continues or reconnects without duplicated text.
7. Click **Stop**.
8. Confirm generation stops, the partial answer remains visible, and the composer becomes usable.
9. Refresh the page and reopen `Thread A`.
10. Confirm the completed or stopped turn appears once, with no duplicate user or assistant messages.

Pass: both threads remain isolated; Thread A's in-flight turn survives the switch; Stop works after returning; no blank transcript or duplicate turn appears.

## P0 - Navigate away during streaming, resume, and stop

Purpose: verify that unmounting `/chat` releases the old browser stream and the remounted page reconnects with a working Stop action.

1. Start another long response in `Thread A`.
2. While it is streaming, navigate to a different NOUS route using the application navigation.
3. Use the browser Back button to return to Thread A.
4. Wait for the response to reconnect or finish.
5. If it is still running, click **Stop**.
6. Confirm Stop takes effect and the composer unlocks.
7. In DevTools, confirm there is not a second concurrently active stream for the same run.

Pass: the chat returns to the same thread, resumes without duplicate content, and Stop controls the resumed stream.

## P0 - Rapid switching must scope load failures to the correct thread

Purpose: verify that a failed request for one thread does not display an error on another successfully loaded thread.

1. Copy Thread A's ID from its URL.
2. In Chrome DevTools, add this Network request-blocking pattern: `*api/v2/threads/<THREAD_A_ID>/messages*`.
3. Hard-refresh on Thread B so the page starts with a clean in-memory cache.
4. Click Thread A and immediately click Thread B before Thread A finishes loading.
5. Wait at least five seconds.
6. Confirm Thread B loads normally and no `Could not load this conversation` toast is shown for Thread B.
7. Click Thread A again with the block still enabled.
8. Confirm exactly one toast appears: `Could not load this conversation. Please try again.`
9. Confirm the loading skeleton settles rather than spinning forever.
10. Disable request blocking, switch to Thread B, then return to Thread A.
11. Confirm Thread A loads successfully and the old error does not reappear.

Pass: the failure is reported only while Thread A is active, only once for that failed request, and a later successful load clears the condition.

## P0 - Deleted deep link must fail visibly and recover

Purpose: verify that a stale or deleted `?thread=` link does not fail silently or loop.

1. Open Thread C and copy its full URL.
2. Delete Thread C from the sidebar and confirm the deletion.
3. Paste the copied URL into the address bar and navigate to it.
4. Confirm exactly one toast appears: `Could not open that conversation. Please try again.`
5. Confirm the dead `?thread=<id>` parameter is removed and the address becomes `/chat` or a valid auto-selected thread URL.
6. Confirm the deleted transcript is never flashed from cache, the page does not loop requests, and the composer remains usable.
7. Hard-refresh and confirm Thread C is still absent from the sidebar.

Pass: the stale link produces one clear error, removes the invalid parameter, shows no cached deleted transcript, and recovers to a usable chat screen.

## P1 - Automatic selection and shareable URL

Purpose: verify that restored or automatically selected threads are reflected in the address bar.

1. Navigate directly to `/chat` with no query string.
2. Wait for initialization.
3. Confirm a conversation is selected and the URL becomes `/chat?thread=<selected-id>`.
4. Copy the URL and open it in a second authenticated tab.
5. Confirm the same conversation and transcript load.
6. Click Thread B and confirm the URL changes to Thread B's ID.
7. Use Back and Forward and confirm the displayed thread always matches the URL.
8. Navigate to `/chat?new=1` and confirm the blank new-chat composer remains selected instead of auto-opening an old thread.

Pass: selected-thread state and URL never disagree; copied links restore the expected thread; explicit new-chat intent stays blank.

## P1 - Single delete cleanup

1. Open a disposable thread containing a distinctive message.
2. Delete it and confirm the dialog.
3. Confirm it disappears from the sidebar immediately.
4. If it was active, confirm the app leaves its URL and shows a usable new-chat state or another valid thread.
5. Use Back, then reopen `/chat`; confirm the deleted thread and its distinctive message do not flash from cache.
6. Hard-refresh and confirm the thread remains absent.

Pass: the server deletion and local sidebar, message, pagination, and active-selection state agree without stale content.

## P1 - Bulk delete cleanup

1. Create or identify two disposable threads; open one so it is active.
2. Enter sidebar select mode and select both threads.
3. Click the bulk-delete control and confirm.
4. Confirm both successfully deleted threads disappear and select mode exits.
5. Confirm an active deleted thread is no longer displayed and its old `?thread=` URL is not retained.
6. Hard-refresh and verify neither deleted thread returns.
7. Confirm an unselected control thread remains intact and opens normally.

Pass: only selected successful deletions are removed, the active selection is cleared when appropriate, and unrelated threads are unchanged.

## P1 - Cached transcript refresh

1. Open Thread A and wait for its transcript to load.
2. Switch to Thread B, then back to Thread A.
3. Confirm Thread A's cached transcript appears immediately while any background refresh runs.
4. Confirm there is no full transcript skeleton, empty-state flash, duplicate message, or stale Thread B content.

Pass: cached content remains readable throughout refresh and the two thread transcripts stay isolated.

## Mobile smoke

At a 390 x 844 viewport:

1. Open the conversation drawer and switch A -> B -> A.
2. Start a response in A, switch to B, return to A, and stop it.
3. Delete one disposable thread.
4. Confirm dialogs, toast messages, sidebar controls, transcript, and composer are visible and usable without horizontal overflow.

## Result record

| ID | Test | Result | Evidence / notes |
| --- | --- | --- | --- |
| P0-1 | Streaming switch, return, and stop | Not run | |
| P0-2 | Navigate away, resume, and stop | Not run | |
| P0-3 | Thread-scoped load failure | Not run | |
| P0-4 | Deleted deep-link recovery | Not run | |
| P1-1 | Automatic selection and URL | Not run | |
| P1-2 | Single delete cleanup | Not run | |
| P1-3 | Bulk delete cleanup | Not run | |
| P1-4 | Cached transcript refresh | Not run | |
| M-1 | Mobile smoke | Not run | |

## Release decision

- **Pass:** all P0 tests pass, no stale or cross-thread content appears, and no new console error or failed request is left unexplained.
- **Conditional pass:** P0 passes and only a cosmetic mobile issue remains, with an owner and follow-up recorded.
- **Fail:** any wrong-thread content, lost/duplicated turn, unresponsive Stop action, silent dead link, infinite loading state, or deleted transcript reappears.

