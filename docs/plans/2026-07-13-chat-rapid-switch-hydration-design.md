# Rapid thread-switch hydration design

## Problem

The authenticated PR preview reproduces a browser-only failure when uncached
threads are selected rapidly. The final URL, sidebar selection, and header all
agree on the selected thread, but the conversation transcript is empty even
though the thread has persisted messages. Selecting another thread slowly and
returning restores the transcript.

The assistant-ui runtime is keyed by `activeThreadId`. On an uncached switch it
therefore mounts immediately with an empty message adapter while the thread is
loading. When the messages arrive, the existing runtime receives the populated
adapter after commit. Under rapid switching, the indexed message consumers can
miss that hydration update and remain empty.

## Scope

This pass is limited to thread-transition correctness and feedback on `/chat`.
It does not redesign the chat layout, typography, composer, context rail, or
message presentation.

## Design

### Runtime lifecycle

Give `ChatRuntimeProvider` a lifecycle key composed from:

- the active thread identity; and
- whether the selected thread is still empty/loading or has hydrated messages.

An uncached thread first mounts an empty runtime while its transcript loads.
When its first persisted messages arrive, the hydration phase changes and React
mounts a fresh runtime whose initial adapter already contains those messages.

The hydrated key remains stable when messages are appended, streamed, retried,
or prepended through pagination. Existing same-thread interaction state is
therefore preserved after initial hydration.

Empty threads remain on the empty phase and do not remount without messages.
Creating the first message in a genuinely empty thread performs one intentional
empty-to-hydrated remount.

### Transition feedback

Keep sidebar selection and the chat header immediate. While an uncached thread
is loading, retain the existing transcript skeleton and expose a concise
`Loading conversation` status to assistive technology. Do not add decorative
motion or delay selection feedback.

### Data flow

1. A sidebar click immediately updates the active conversation and store thread.
2. The store load epoch makes older message responses stale.
3. The selected thread renders its empty/loading runtime phase and skeleton.
4. The newest thread response populates store-backed displayed messages.
5. The runtime key changes once to the hydrated phase and mounts with the final
   selected thread's messages already present.
6. Later same-thread message changes update the existing hydrated runtime.

### Error handling

The existing load error path remains authoritative. This design does not hide
API failures or retain the previous thread's transcript. A failed uncached load
stays empty and surfaces the existing store/session error behavior.

## Verification

- Red-green component regression for empty-to-hydrated provider remount.
- Same-thread hydrated message updates preserve the provider instance.
- Thread identity changes still remount the provider.
- Focused assistant-ui and thread-switch unit suites pass.
- Full frontend tests, TypeScript, lint, and `git diff --check` pass.
- Authenticated preview stress test alternates real uncached sidebar selections,
  then verifies no global error and that the final transcript contains the
  selected thread's messages.
