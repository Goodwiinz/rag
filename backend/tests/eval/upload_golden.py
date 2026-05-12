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


def _example_payload(case: GoldenCase) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs: dict[str, Any] = {"question": case.question}
    if case.page_context:
        inputs["page_context"] = case.page_context

    outputs: dict[str, Any] = {
        "intent": case.expected_intent,
        "expected_tools": list(case.expected_tools),
        "tool_match": case.tool_match,
        "accept_intents": list(case.accept_intents),
    }
    if case.expected_answer:
        outputs["expected_answer"] = case.expected_answer
    metadata: dict[str, Any] = {"golden_case": case.name, **case.metadata}
    return inputs, outputs, metadata


def upload(dataset_name: str) -> None:
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

    existing_names = {
        (ex.metadata or {}).get("golden_case")
        for ex in client.list_examples(dataset_id=dataset.id)
    }

    created = 0
    skipped = 0
    for case in ALL_CASES:
        if case.name in existing_names:
            skipped += 1
            continue
        inputs, outputs, metadata = _example_payload(case)
        client.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset.id,
            metadata=metadata,
        )
        created += 1
        print(f"  + {case.name}")

    print(f"Done. created={created} skipped={skipped} total_local={len(ALL_CASES)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=os.environ.get("AGENT_EVAL_DATASET_NAME", "agent-accuracy-benchmark"),
        help="LangSmith dataset name (default: agent-accuracy-benchmark)",
    )
    args = parser.parse_args()
    upload(args.dataset)


if __name__ == "__main__":
    main()
