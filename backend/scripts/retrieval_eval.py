"""Retrieval-quality gate: recall@k + rerank lift over hand-labeled qrels.

Usage:
  python -m scripts.retrieval_eval --org-id <uuid> [--k 3 5] [--rerank both|on|off] [--dump]

Read-only against the live dev DO KB + DB (Infisical /do-kb env). Drives
cases through the SAME funnel the agent uses in production:
``client.retrieve`` -> ``resolve_and_filter_chunks`` -> optional
``cohere_rescore_chunks`` — instrumenting ``hybrid_search_service`` instead
would measure a path the agent doesn't take.

This is an operator gate, not a CI gate: it always exits 0 (see main()).

No project/user ownership guard on --org-id: this is an operator CLI run
directly against Infisical dev creds by a human who already has DB access,
not a request handler serving an untrusted caller — unlike
``_tool_do_kb_retrieve``/the rag_node, there is nothing here that needs
``_verify_project_ownership``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from uuid import UUID

from src.core.database import AsyncSessionLocal
from src.models.organization import Organization
from src.services.do_kb import get_do_kb_client
from src.services.do_kb.rerank import cohere_rescore_chunks
from src.services.do_kb.resolve import resolve_and_filter_chunks
from src.services.search.search_quality_service import SearchQualityService
from tests.eval.retrieval_qrels import CASES, RetrievalCase


@dataclass
class _EvalResult:
    document_id: str


@dataclass
class _EvalShim:
    results: list


def _recall_at_k(ranked_ids: list[str], relevant: tuple[str, ...], k: int) -> float:
    """recall@k, wired through the existing SearchQualityService math via a
    typed shim (SearchResponse has ~14 required fields; _calculate_recall
    only ever reads ``.results[*].document_id``)."""
    shim = _EvalShim([_EvalResult(d) for d in ranked_ids[:k]])
    return SearchQualityService()._calculate_recall(shim, list(relevant))


def _mrr(ranked_ids: list[str], relevant: tuple[str, ...]) -> float:
    """Reciprocal rank of the first relevant doc id; 0.0 if none present.
    Recall@8 over an 8-result list can't see reordering — this is the
    rerank-lift detector."""
    for rank, doc_id in enumerate(ranked_ids):
        if doc_id in relevant:
            return 1.0 / (rank + 1)
    return 0.0


def _ranked_doc_ids(title_by_key: dict, chunks: list) -> list[str]:
    """Chunk order -> deduped, order-preserving list of resolved Document ids."""
    ids: list[str] = []
    for c in chunks:
        doc_id = title_by_key.get(c.document_id or "", (None, None))[0]
        if doc_id and doc_id not in ids:
            ids.append(doc_id)
    return ids


async def _run_case(
    case: RetrievalCase,
    *,
    org_id: UUID,
    kb_uuid: str,
    session,
    ks: list[int],
    rerank: str,
    dump: bool,
) -> dict:
    client = get_do_kb_client()
    result = await client.retrieve(kb_uuid=kb_uuid, query=case.query)
    title_by_key, chunks = await resolve_and_filter_chunks(
        chunks=result.chunks,
        org_id=org_id,
        session=session,
        project_id=case.project_id,
    )

    if dump:
        print(f"\n=== {case.name}: {case.query!r} ===")
        for c in chunks:
            doc_id, title = title_by_key.get(c.document_id or "", (None, None))
            print(
                f"  {doc_id or c.document_id!r:38}  score={c.score:.3f}  {title or ''}"
            )
        return {}

    row: dict = {"name": case.name}
    if rerank in ("both", "off"):
        off_ids = _ranked_doc_ids(title_by_key, chunks)
        for k in ks:
            row[f"recall@{k}_off"] = _recall_at_k(off_ids, case.relevant_doc_ids, k)
        row["mrr_off"] = _mrr(off_ids, case.relevant_doc_ids)
    if rerank in ("both", "on"):
        reranked = await cohere_rescore_chunks(case.query, list(chunks))
        on_ids = _ranked_doc_ids(title_by_key, reranked)
        for k in ks:
            row[f"recall@{k}_on"] = _recall_at_k(on_ids, case.relevant_doc_ids, k)
        row["mrr_on"] = _mrr(on_ids, case.relevant_doc_ids)
    return row


def _print_table(rows: list[dict], ks: list[int], rerank: str) -> None:
    metrics = [f"recall@{k}" for k in ks] + ["mrr"]
    variants = ["off", "on"] if rerank == "both" else [rerank]
    header = "case".ljust(30) + "".join(
        f"{m}({v})".rjust(16) for m in metrics for v in variants
    )
    print(f"\n{header}")
    totals = {f"{m}_{v}": 0.0 for m in metrics for v in variants}
    for row in rows:
        line = row["name"][:29].ljust(30)
        for m in metrics:
            for v in variants:
                val = row.get(f"{m}_{v}", 0.0)
                totals[f"{m}_{v}"] += val
                line += f"{val:.3f}".rjust(16)
        print(line)
    if rows:
        line = "MEAN".ljust(30)
        for m in metrics:
            for v in variants:
                line += f"{totals[f'{m}_{v}'] / len(rows):.3f}".rjust(16)
        print(line)
    if rerank == "both":
        print("\nΔ (on - off), mean:")
        for m in metrics:
            delta = (totals[f"{m}_on"] - totals[f"{m}_off"]) / max(len(rows), 1)
            print(f"  {m}: {delta:+.3f}")


async def _run(args: argparse.Namespace) -> int:
    if not CASES:
        print(
            "no cases labeled yet — run with --dump against the dev org and "
            "hand-label (see tests/eval/retrieval_qrels.py docstring)"
        )
        return 0

    org_id = UUID(args.org_id)
    async with AsyncSessionLocal() as session:
        org = await session.get(Organization, org_id)
        kb_uuid = getattr(org, "do_kb_uuid", None) if org else None
        if not kb_uuid:
            print(f"ERROR: org {org_id} has no provisioned do_kb_uuid", file=sys.stderr)
            return 0

        rows = []
        for case in CASES:
            row = await _run_case(
                case,
                org_id=org_id,
                kb_uuid=kb_uuid,
                session=session,
                ks=args.k,
                rerank=args.rerank,
                dump=args.dump,
            )
            if row:
                rows.append(row)

    if not args.dump:
        _print_table(rows, args.k, args.rerank)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="retrieval-eval",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--org-id", required=True, help="Organization UUID")
    parser.add_argument(
        "--k",
        type=int,
        nargs="+",
        default=[3, 5],
        help="recall@k cutoffs (default: 3 5)",
    )
    parser.add_argument(
        "--rerank",
        choices=["both", "on", "off"],
        default="both",
        help="Score DO order (off), Cohere-reranked order (on), or both (default)",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Print resolved (doc_id, title, score) candidates per case for labeling; no scoring",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
