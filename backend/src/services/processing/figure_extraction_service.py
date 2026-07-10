"""PyMuPDF-based figure extraction. Phase 1: embedded raster images + caption
heuristics. No models, bounded per-page work. Docling is the phase-2 upgrade."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import fitz
import structlog
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models.document import Document, DocumentType
from src.models.document_processing import ContentType, MultimodalContent
from src.services.documents.storage_utils import local_file_for_document

logger = structlog.get_logger()

FIGURES_SECTION_MARKER = "\n\n## Extracted figures\n"
EXTRACTION_METHOD = "pymupdf_figures"  # discriminator for rows + delete-before-insert
MIN_DIM_PX = 64  # skip icons/decorations
MAX_FIGURES_PER_DOC = 50  # hard bound on work + rows
CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?\.?\s*\d+)[.:]?\s*", re.IGNORECASE)


def merge_captions_into_text(existing: Optional[str], captions_text: str) -> str:
    """Strip any prior FIGURES_SECTION_MARKER section, then append the new one.
    Idempotent under re-runs even when content_text wasn't rebuilt."""
    base = (existing or "").split(FIGURES_SECTION_MARKER)[0].rstrip()
    return f"{base}{captions_text}" if captions_text else base


def _collect_candidates(pdf_doc: "fitz.Document") -> List[Dict[str, Any]]:
    """Walk every page collecting raster + caption-only figure candidates,
    rendering PNG crops for raster candidates while the document is open.

    Ordered by page; bounded to MAX_FIGURES_PER_DOC total candidates.
    """
    candidates: List[Dict[str, Any]] = []
    seen_xrefs: set = set()

    for page_index in range(len(pdf_doc)):
        if len(candidates) >= MAX_FIGURES_PER_DOC:
            break

        page = pdf_doc.load_page(page_index)
        page_no = page_index + 1

        page_images = []
        for info in page.get_image_info(xrefs=True):
            width, height = info.get("width", 0), info.get("height", 0)
            xref = info.get("xref")
            if width < MIN_DIM_PX or height < MIN_DIM_PX:
                continue
            if not xref or xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            page_images.append(
                {
                    "xref": xref,
                    "bbox": list(info["bbox"]),
                    "width": width,
                    "height": height,
                }
            )

        page_captions = []
        for block in page.get_text("blocks"):
            if len(block) < 7 or block[6] != 0:
                continue  # not a text block
            text = (block[4] or "").strip()
            match = CAPTION_RE.match(text)
            if not match:
                continue
            page_captions.append(
                {
                    "bbox": list(block[:4]),
                    "label": match.group(1).strip(),
                    # Body only — the label is stored separately (figure_label)
                    # and captions_text renders "[<label>, p.N] <body>", so
                    # keeping the label here would duplicate it.
                    "text": text[match.end() :].strip(),
                }
            )

        used_captions: set = set()
        for img in page_images:
            if len(candidates) >= MAX_FIGURES_PER_DOC:
                break
            best_idx, best_gap = None, None
            iy0, iy1 = img["bbox"][1], img["bbox"][3]
            for idx, cap in enumerate(page_captions):
                if idx in used_captions:
                    continue
                cy0, cy1 = cap["bbox"][1], cap["bbox"][3]
                if cy0 >= iy1:
                    gap = cy0 - iy1  # caption below image
                elif cy1 <= iy0:
                    gap = iy0 - cy1  # caption above image
                else:
                    gap = 0.0  # overlapping
                if best_gap is None or gap < best_gap:
                    best_idx, best_gap = idx, gap

            caption = page_captions[best_idx] if best_idx is not None else None
            if caption is not None:
                used_captions.add(best_idx)

            pix = fitz.Pixmap(pdf_doc, img["xref"])
            if pix.n - pix.alpha > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            png_bytes = pix.tobytes("png")
            pix = None  # drop each iteration, bounded memory

            candidates.append(
                {
                    "kind": "raster",
                    "page": page_no,
                    "xref": img["xref"],
                    "bbox": img["bbox"],
                    "width": img["width"],
                    "height": img["height"],
                    "caption_text": caption["text"] if caption else None,
                    "label": caption["label"] if caption else None,
                    "png_bytes": png_bytes,
                }
            )

        for idx, cap in enumerate(page_captions):
            if idx in used_captions or len(candidates) >= MAX_FIGURES_PER_DOC:
                continue
            candidates.append(
                {
                    "kind": "caption",
                    "page": page_no,
                    "xref": None,
                    "bbox": cap["bbox"],
                    "width": None,
                    "height": None,
                    "caption_text": cap["text"],
                    "label": cap["label"],
                    "png_bytes": None,
                }
            )

    return candidates


def extract_figures_for_document(db: Session, document: Document) -> Dict[str, Any]:
    """Idempotent. Returns {"figures_extracted": int, "captions_found": int,
    "captions_text": str, "skipped": Optional[str]}. Raises only on unexpected
    errors (callers treat the step as optional)."""
    if not settings.FIGURE_EXTRACTION_ENABLED:
        return {"skipped": "disabled"}
    if document.document_type != DocumentType.PDF:
        return {"skipped": "not_pdf"}

    with local_file_for_document(document) as pdf_path:
        pdf_doc = fitz.open(pdf_path)
        try:
            candidates = _collect_candidates(pdf_doc)
        finally:
            pdf_doc.close()

    helper = None
    try:
        from src.core.s3_client import S3StorageHelper

        helper = S3StorageHelper()
    except RuntimeError:
        logger.warning(
            "figure_extraction_s3_unconfigured",
            document_id=str(document.id),
        )

    uploaded_keys: List[str] = []
    rows: List[MultimodalContent] = []
    caption_lines: List[str] = []

    try:
        for i, cand in enumerate(candidates):
            is_raster = cand["kind"] == "raster"
            content_id = (
                f"figure-p{cand['page']}-x{cand['xref']}"
                if is_raster
                else f"figure-p{cand['page']}-c{i}"
            )

            storage_key = None
            if is_raster and helper is not None:
                storage_key = (
                    f"figures/{document.organization_id}/{document.id}/{content_id}.png"
                )
                helper.upload_file(
                    storage_key, cand["png_bytes"], content_type="image/png"
                )
                uploaded_keys.append(storage_key)

            caption_text = cand["caption_text"]
            rows.append(
                MultimodalContent(
                    document_id=document.id,
                    organization_id=document.organization_id,
                    content_type=ContentType.IMAGE,
                    content_id=content_id,
                    sequence_order=i,
                    raw_content=caption_text or None,
                    processed_content=caption_text or None,
                    content_metadata={
                        "kind": "figure",
                        "page": cand["page"],
                        "bbox": cand["bbox"],
                        "storage_key": storage_key,
                        "figure_label": cand["label"],
                    },
                    media_dimensions=(
                        {"width": cand["width"], "height": cand["height"]}
                        if is_raster
                        else None
                    ),
                    media_format="png" if is_raster else None,
                    extraction_method=EXTRACTION_METHOD,
                    extraction_confidence=0.6,
                )
            )

            if caption_text:
                caption_lines.append(
                    f"[{cand['label']}, p.{cand['page']}] {caption_text}"
                )
    except Exception:
        for key in uploaded_keys:
            try:
                helper.delete_file(key)
            except Exception:
                logger.warning(
                    "figure_extraction_compensating_delete_failed",
                    key=key,
                    document_id=str(document.id),
                )
        raise

    db.query(MultimodalContent).filter(
        MultimodalContent.document_id == document.id,
        MultimodalContent.organization_id == document.organization_id,
        MultimodalContent.extraction_method == EXTRACTION_METHOD,
    ).delete(synchronize_session=False)
    for row in rows:
        db.add(row)

    captions_text = (
        FIGURES_SECTION_MARKER + "\n".join(caption_lines) + "\n"
        if caption_lines
        else ""
    )

    return {
        "figures_extracted": sum(1 for c in candidates if c["kind"] == "raster"),
        "captions_found": len(caption_lines),
        "captions_text": captions_text,
    }
