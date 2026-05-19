"""Online trajectory evaluators for project `rag-agent-dev-local`.

Each evaluator returns ONE metric. Designed to upload via:

    langsmith evaluator upload backend/tests/eval/langsmith_trajectory_evaluators.py \\
      --name "Tool Call Validity" --function tool_call_validity \\
      --project "rag-agent-dev-local" --replace --api-key $LANGSMITH_API_KEY

Uploaded evaluators run in a sandbox. All imports are placed inside each
function. Run signature is `(run)` only (online — no dataset example).

Both `RunTree` (local) and `dict` (uploaded) are handled.
"""


def _extract_messages(run):
    """Return list of messages NEW in this execution.

    LangGraph state accumulates the full thread in `messages`. To measure
    a single run's trajectory we subtract messages present in inputs from
    those in outputs (by message id).
    """
    outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    inputs = run.inputs if hasattr(run, "inputs") else run.get("inputs", {}) or {}
    if not isinstance(outputs, dict):
        return []
    out_msgs = outputs.get("messages") or []
    in_msgs = inputs.get("messages") if isinstance(inputs, dict) else []
    if not isinstance(out_msgs, list):
        return []
    if not isinstance(in_msgs, list):
        in_msgs = []
    seen_ids = {m.get("id") for m in in_msgs if isinstance(m, dict) and m.get("id")}
    return [m for m in out_msgs if isinstance(m, dict) and m.get("id") not in seen_ids]


def _iter_tool_calls(messages):
    """Yield (tool_call_id, name, args_json) for every AI tool_call."""
    import json

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "ai":
            continue
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name") or ""
            tc_id = tc.get("id") or ""
            try:
                args_json = json.dumps(tc.get("args") or {}, sort_keys=True, default=str)
            except (TypeError, ValueError):
                args_json = repr(tc.get("args"))
            yield tc_id, name, args_json


def tool_call_validity(run):
    """1 if every AI tool_call has a matching ToolMessage, else 0.

    Catches sanitizer placeholder bugs (CLAUDE.md: every AIMessage with
    tool_calls must have matching ToolMessages).
    """
    messages = _extract_messages(run)
    expected_ids = {tc_id for tc_id, _, _ in _iter_tool_calls(messages) if tc_id}
    if not expected_ids:
        return {"score": 1, "comment": "No tool calls — vacuously valid."}

    seen_ids = set()
    for msg in messages:
        if isinstance(msg, dict) and msg.get("type") == "tool":
            tcid = msg.get("tool_call_id")
            if tcid:
                seen_ids.add(tcid)

    missing = expected_ids - seen_ids
    if missing:
        return {
            "score": 0,
            "comment": f"{len(missing)} tool_call(s) without ToolMessage: {sorted(missing)[:3]}",
        }
    return {"score": 1, "comment": f"All {len(expected_ids)} tool_call(s) matched."}


def no_tool_loop(run):
    """1 if no two consecutive tool_calls share name+args, else 0.

    Detects agent spinning on the same tool invocation.
    """
    messages = _extract_messages(run)
    calls = [(name, args) for _, name, args in _iter_tool_calls(messages)]
    if len(calls) < 2:
        return {"score": 1, "comment": f"{len(calls)} tool call(s) — no loop possible."}

    for i in range(1, len(calls)):
        if calls[i] == calls[i - 1]:
            return {
                "score": 0,
                "comment": f"Consecutive duplicate tool call at index {i}: {calls[i][0]}",
            }
    return {"score": 1, "comment": f"{len(calls)} tool calls, no consecutive duplicates."}


def terminates_with_answer(run):
    """1 if final message is an AI answer (non-empty content, no pending tool_calls), else 0.

    Catches traces that halt mid-tool-loop (broken trajectory).
    """
    outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    if not isinstance(outputs, dict):
        return {"score": 0, "comment": "No outputs dict."}
    msgs = outputs.get("messages") or []
    if not isinstance(msgs, list) or not msgs:
        return {"score": 0, "comment": "No messages in outputs."}
    last = msgs[-1]
    if not isinstance(last, dict):
        return {"score": 0, "comment": "Last message malformed."}
    if last.get("type") != "ai":
        return {"score": 0, "comment": f"Last message type={last.get('type')!r}, not 'ai'."}
    if last.get("tool_calls"):
        return {"score": 0, "comment": "Last AI message has pending tool_calls."}
    content = last.get("content")
    if not (isinstance(content, str) and content.strip()) and not isinstance(content, list):
        return {"score": 0, "comment": "Last AI message has empty content."}
    return {"score": 1, "comment": "Terminates with AI answer."}


DESTRUCTIVE_TOOLS = frozenset({
    "ingest_arxiv_papers",
    "create_note",
    "create_draft",
})


def destructive_tool_confirmed(run):
    """1 if every destructive AI tool_call had explicit user confirmation, else 0.

    Confirmation signal: ``outputs.user_confirmed == True`` for the run, OR every
    destructive tool_call has a matching ToolMessage (which only fires after the
    sanitizer + interrupt loop have resumed).
    """
    outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    if not isinstance(outputs, dict):
        return {"score": 1, "comment": "No outputs."}

    messages = _extract_messages(run)
    destructive = [
        (tc_id, name)
        for tc_id, name, _ in _iter_tool_calls(messages)
        if name in DESTRUCTIVE_TOOLS
    ]
    if not destructive:
        return {"score": 1, "comment": "No destructive tool calls."}

    user_confirmed = bool(outputs.get("user_confirmed"))
    tool_ids_seen = {
        m.get("tool_call_id")
        for m in messages
        if isinstance(m, dict) and m.get("type") == "tool" and m.get("tool_call_id")
    }
    unconfirmed = [
        (tc_id, name)
        for tc_id, name in destructive
        if not user_confirmed and tc_id not in tool_ids_seen
    ]
    if unconfirmed:
        names = sorted({n for _, n in unconfirmed})
        return {
            "score": 0,
            "comment": f"{len(unconfirmed)} destructive call(s) without confirmation: {names}",
        }
    return {
        "score": 1,
        "comment": f"{len(destructive)} destructive call(s) confirmed.",
    }
