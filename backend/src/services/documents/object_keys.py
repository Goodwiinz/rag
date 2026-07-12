"""Deterministic Spaces/S3 object-key derivations for a document's objects.

A single document accumulates three object classes in Spaces:

* originals   — ``{documents,images,audio,video}/{org}/{doc}/…`` (``storage_path``)
* KB text     — ``documents/{org}/{doc}.txt`` (canonical DO-KB text mirror)
* figure PNGs — ``figures/{org}/{doc}/{content_id}.png``

The exact keys are constructed in several places (KB ingest writes the text
mirror, figure extraction writes the PNGs) and must be re-derived elsewhere to
clean them up (the delete path) and to audit them (the storage reconciler). This
module is the ONE source of truth for those derivations, so cleanup/audit can't
drift from what the writers produce — a drift would leak retained user content
after delete (audit finding D6).

Kept deliberately dependency-light (no PDF/ML/service imports) so the delete
path and the reconciler can derive keys without dragging in the heavy
extraction/ingest packages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.document import Document

# Top-level Spaces prefixes.
DOCUMENTS_KEY_PREFIX = "documents"  # originals (type=documents) + KB text mirror
FIGURES_KEY_PREFIX = "figures"  # figure PNG crops


def canonical_text_key(document: "Document") -> str:
    """``documents/{org}/{doc}.txt`` — the canonical DO-KB text mirror's key.

    Referenced even when the mirror was never uploaded (DO_KB off / no
    ``content_text``): the key is deterministic from the document id, so callers
    can always derive it.
    """
    return f"{DOCUMENTS_KEY_PREFIX}/{document.organization_id}/{document.id}.txt"


def figure_object_prefix(document: "Document") -> str:
    """``figures/{org}/{doc}/`` — the prefix every figure PNG crop for a
    document is written under.

    The prefix embeds the document UUID, so listing under it can only ever match
    THIS document's own figures — the delete path relies on that to remove
    exactly this document's crops.
    """
    return f"{FIGURES_KEY_PREFIX}/{document.organization_id}/{document.id}/"


def figure_object_key(document: "Document", content_id: str) -> str:
    """Deterministic key of a single figure PNG crop under the doc prefix."""
    return f"{figure_object_prefix(document)}{content_id}.png"
