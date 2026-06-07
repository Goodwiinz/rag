"""Upload golden Q&A cases to a LangSmith dataset.

Idempotent: creates the dataset if absent, then upserts examples by name.

Usage:

    LANGCHAIN_API_KEY=... python -m tests.eval.upload_golden
    LANGCHAIN_API_KEY=... python -m tests.eval.upload_golden --dataset agent-accuracy-benchmark
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from tests.eval.golden_examples import ALL_CASES, GoldenCase


def _partition_examples(
    examples: Any, local_names: set[str]
) -> tuple[dict[str, Any], list[Any]]:
    """Split remote examples into known-by-name and orphans.

    Returns ``(by_name, orphans)`` where ``by_name`` maps each local golden
    case name to its single canonical remote example, and ``orphans`` is every
    other row: unknown ``golden_case``, missing metadata, or a *duplicate* of
    an already-seen name.

    Orphans are a LIST, not a dict keyed on ``golden_case``: the polluted rows
    this exists to clean (pytest-langsmith fixture-arg leaks, ``case``-nested
    capture) all share a missing ``golden_case``, so a dict would collapse them
    to one ``None`` key and ``--clean`` would delete only one of many.
    """
    by_name: dict[str, Any] = {}
    orphans: list[Any] = []
    for ex in examples:
        name = (getattr(ex, "metadata", None) or {}).get("golden_case")
        if name in local_names and name not in by_name:
            by_name[name] = ex
        else:
            orphans.append(ex)
    return by_name, orphans


def _example_payload(case: GoldenCase) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs: dict[str, Any] = {"question": case.question}
    if case.page_context:
        inputs["page_context"] = case.page_context

    outputs: dict[str, Any] = {
        "intent": case.expected_intent,
        "expected_tools": list(case.expected_tools),
    }
    metadata: dict[str, Any] = {"golden_case": case.name, **case.metadata}
    return inputs, outputs, metadata


def upload(dataset_name: str, *, clean: bool = False) -> None:
    """Upsert every local golden case into *dataset_name*.

    True upsert (the old version was create-only, which is why a polluted
    dataset never self-healed): existing examples are UPDATED to match the
    local case, missing ones are created, and — when ``clean=True`` — orphan
    rows (any example whose ``golden_case`` metadata is not in ``ALL_CASES``,
    including the pytest-langsmith fixture-arg-leak and ``case``-nested
    pollution) are DELETED so the remote dataset exactly mirrors local.
    """
    if not os.environ.get("LANGCHAIN_API_KEY"):
        print("LANGCHAIN_API_KEY not set; aborting.", file=sys.stderr)
        sys.exit(1)

    from langsmith import Client

    client = Client()

    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
        print(f"Using existing dataset: {dataset_name} (id={dataset.id})")
    except Exception:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="Agent regression — golden Q&A across intent, tool routing, do_kb",
        )
        print(f"Created dataset: {dataset_name} (id={dataset.id})")

    local_names = {case.name for case in ALL_CASES}
    existing_by_name, orphans = _partition_examples(
        client.list_examples(dataset_id=dataset.id), local_names
    )
    created = updated = deleted = 0

    for case in ALL_CASES:
        inputs, outputs, metadata = _example_payload(case)
        existing = existing_by_name.get(case.name)
        if existing is not None:
            client.update_example(
                example_id=existing.id,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
            )
            updated += 1
            print(f"  ~ {case.name}")
        else:
            client.create_example(
                inputs=inputs,
                outputs=outputs,
                dataset_id=dataset.id,
                metadata=metadata,
            )
            created += 1
            print(f"  + {case.name}")

    if clean:
        for ex in orphans:
            client.delete_example(example_id=ex.id)
            deleted += 1
            name = (getattr(ex, "metadata", None) or {}).get("golden_case")
            print(f"  - orphan: golden_case={name!r} (id={ex.id})")

    print(
        f"Done. created={created} updated={updated} deleted={deleted} "
        f"total_local={len(ALL_CASES)}"
        + ("" if clean else "  (run with --clean to delete orphan rows)")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=os.environ.get("AGENT_EVAL_DATASET_NAME", "agent-accuracy-benchmark"),
        help="LangSmith dataset name (default: agent-accuracy-benchmark)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete orphan rows (examples not in ALL_CASES) so the remote "
        "dataset exactly mirrors local golden cases.",
    )
    args = parser.parse_args()
    upload(args.dataset, clean=args.clean)


if __name__ == "__main__":
    main()
