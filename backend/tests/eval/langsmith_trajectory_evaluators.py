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
    # Orphan ToolMessage: a result whose tool_call_id has no originating AI
    # tool_call in this turn (_extract_messages already scopes to new messages,
    # so a cross-turn result is not flagged). Signals a malformed/mis-stitched
    # trajectory the sanitizer should have caught.
    orphans = seen_ids - expected_ids
    if orphans:
        return {
            "score": 0,
            "comment": f"{len(orphans)} ToolMessage(s) without originating tool_call: {sorted(orphans)[:3]}",
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

    # Non-consecutive spinning: an A,B,A,B oscillation or the same identical-args
    # call repeated with other steps interleaved is NOT caught by the adjacent
    # check above. Flag when any identical (name, args) appears >=3 times across
    # the whole trajectory. Threshold 3 leaves a single legitimate retry alone.
    from collections import Counter

    worst, n = Counter(calls).most_common(1)[0]
    if n >= 3:
        return {
            "score": 0,
            "comment": f"Tool call {worst[0]} repeated {n}x with identical args across trajectory.",
        }
    return {"score": 1, "comment": f"{len(calls)} tool calls, no spinning detected."}


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
    if isinstance(content, str):
        if not content.strip():
            return {"score": 0, "comment": "Last AI message has empty content."}
    elif isinstance(content, list):
        # Anthropic/multimodal content is list-shaped. Require at least one
        # non-empty text block — an empty list, a tool_use-only block list, or
        # whitespace-only text blocks are NOT a real terminating answer. (The
        # old `not isinstance(content, list)` short-circuit passed ALL lists.)
        has_text = any(
            (isinstance(b, str) and b.strip())
            or (
                isinstance(b, dict)
                and b.get("type") == "text"
                and (b.get("text") or "").strip()
            )
            for b in content
        )
        if not has_text:
            return {"score": 0, "comment": "Last AI message has no non-empty text block."}
    else:
        return {"score": 0, "comment": "Last AI message has empty content."}
    return {"score": 1, "comment": "Terminates with AI answer."}


def plan_adherence(run):
    """Fraction of planned tool-steps the agent actually executed, in order.

    The planner (``planner.py``) emits an advisory ``plan`` — a list of steps
    ``{step, description, tool, args_hint, depends_on}`` — only for project-
    scoped, multi-step queries; it legitimately skips most turns (greetings,
    simple adds), leaving ``plan == []``. So:

    - empty / no-tool plan  -> score 1 (vacuously adherent — nothing to follow)
    - plan with tool steps  -> score = (planned tool-steps that appear in the
      executed tool calls, IN PLANNED ORDER) / (total planned tool-steps);
      1.0 iff all executed in order, 0.0 if none.

    Deterministic by design: a pure-LLM judge is what made the prior
    plan_adherence attempt fire 0x. Semantic step<->call mapping (tool-name
    drift, paraphrase) is a future refinement layered on this spine.
    """
    outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    if not isinstance(outputs, dict):
        return {"score": 1, "comment": "No outputs dict — vacuously adherent."}

    plan = outputs.get("plan") or []
    planned_tools = [
        step.get("tool")
        for step in plan
        if isinstance(step, dict) and step.get("tool")
    ]
    if not planned_tools:
        return {"score": 1, "comment": "Empty / no-tool plan — vacuously adherent."}

    messages = _extract_messages(run)
    executed = [name for _, name, _ in _iter_tool_calls(messages) if name]

    idx = 0
    for name in executed:
        if idx < len(planned_tools) and name == planned_tools[idx]:
            idx += 1

    score = idx / len(planned_tools)
    if idx == len(planned_tools):
        return {
            "score": 1,
            "comment": f"All {idx} planned tool-step(s) executed in order.",
        }
    return {
        "score": round(score, 3),
        "comment": (
            f"{idx}/{len(planned_tools)} planned tool-step(s) executed in order; "
            f"planned={planned_tools} executed={executed}"
        ),
    }
