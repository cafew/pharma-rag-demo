import re
from pathlib import Path
from typing import List, Tuple

import fitz
from PIL import Image, ImageDraw


def normalize_phrase(text: str) -> str:
    """Normalize spaces for page search."""
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_noise_term(term: str) -> bool:
    """Skip terms that are likely to create noisy highlights."""
    normalized = normalize_phrase(term).lower()
    if not normalized:
        return True

    if any(marker in normalized for marker in ("http://", "https://", "www.")):
        return True

    if "/" in normalized and re.search(r"[a-z]", normalized):
        return True

    if re.fullmatch(r"[\W_]+", normalized):
        return True

    return False


def get_pdf_page_count(pdf_path: Path) -> int:
    """Return the number of pages in the PDF."""
    with fitz.open(pdf_path) as document:
        return len(document)


def build_search_terms(question: str = "", selected_text: str = "", max_terms: int = 8) -> List[str]:
    """Build simple search terms from the query and the selected chunk."""
    candidates: List[str] = []

    question = normalize_phrase(question)
    selected_text = normalize_phrase(selected_text)

    if question:
        candidates.append(question[:40])
        for token in re.split(r"[\s/、，,。．!?！？:：;；()（）\[\]【】]+", question):
            token = normalize_phrase(token)
            if len(token) >= 2 and not is_noise_term(token):
                candidates.append(token[:30])
    elif selected_text:
        fragments = re.split(r"[。．.!?！？\n\r;；:：、，,]+", selected_text)
        fragments = [normalize_phrase(fragment) for fragment in fragments if normalize_phrase(fragment)]
        fragments = sorted(fragments, key=len)
        for fragment in fragments[:4]:
            if 4 <= len(fragment) <= 40 and not is_noise_term(fragment):
                candidates.append(fragment)
            elif len(fragment) > 40 and not is_noise_term(fragment):
                candidates.append(fragment[:40])

        if len(candidates) < max_terms and len(selected_text) >= 8:
            fallback = selected_text[:24]
            if not is_noise_term(fallback):
                candidates.append(fallback)

    terms: List[str] = []
    seen = set()
    for candidate in candidates:
        key = candidate.lower()
        if candidate and key not in seen:
            seen.add(key)
            terms.append(candidate)
        if len(terms) >= max_terms:
            break

    return terms


def deduplicate_rects(rects: List[fitz.Rect]) -> List[fitz.Rect]:
    """Remove duplicate rectangles returned by page.search_for."""
    unique_rects: List[fitz.Rect] = []
    seen = set()

    for rect in rects:
        key = tuple(round(value, 2) for value in (rect.x0, rect.y0, rect.x1, rect.y1))
        if key in seen:
            continue
        seen.add(key)
        unique_rects.append(rect)

    return unique_rects


def render_annotated_page(
    pdf_path: Path,
    page_number: int,
    question: str = "",
    selected_text: str = "",
    zoom: float = 2.0,
) -> Tuple[Image.Image, List[str], int]:
    """Render a PDF page and draw red rectangles on matched text."""
    if page_number < 1:
        raise ValueError("page_number must be 1 or greater.")

    with fitz.open(pdf_path) as document:
        if page_number > len(document):
            raise ValueError(f"page_number exceeds total pages: {len(document)}")

        page = document.load_page(page_number - 1)
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples).convert("RGBA")
        draw = ImageDraw.Draw(image, "RGBA")

        terms = build_search_terms(question=question, selected_text=selected_text)
        rects: List[fitz.Rect] = []

        for term in terms:
            try:
                rects.extend(page.search_for(term))
            except Exception:
                continue

        rects = deduplicate_rects(rects)
        scale_x = image.width / page.rect.width
        scale_y = image.height / page.rect.height

        for rect in rects:
            draw.rectangle(
                [
                    rect.x0 * scale_x,
                    rect.y0 * scale_y,
                    rect.x1 * scale_x,
                    rect.y1 * scale_y,
                ],
                outline=(255, 0, 0, 255),
                width=4,
            )

    return image, terms, len(rects)
