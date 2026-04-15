import os
import re
from pathlib import Path
from typing import Dict, List

import chromadb
import fitz
from dotenv import load_dotenv
from openai import APIError, AuthenticationError, OpenAI, RateLimitError


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = BASE_DIR / "db"
PDF_PATH = DATA_DIR / "manual.pdf"
COLLECTION_NAME = "pharma_manual"
TARGET_CHARS = 900
OVERLAP_PARAGRAPHS = 1


def get_embedding_model() -> str:
    """Read the embedding model after environment variables are loaded."""
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def normalize_text(text: str) -> str:
    """Collapse extra spaces while keeping paragraph boundaries readable."""
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_long_paragraph(paragraph: str, max_chars: int = 500) -> List[str]:
    """Break very long paragraphs into smaller pieces for embedding."""
    paragraph = normalize_text(paragraph)
    if len(paragraph) <= max_chars:
        return [paragraph] if paragraph else []

    parts = re.split(r"(?<=[。．.!?！？])", paragraph)
    chunks: List[str] = []
    buffer = ""

    for part in parts:
        part = normalize_text(part)
        if not part:
            continue

        if len(part) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            for start in range(0, len(part), max_chars):
                segment = normalize_text(part[start : start + max_chars])
                if segment:
                    chunks.append(segment)
            continue

        if buffer and len(buffer) + len(part) > max_chars:
            chunks.append(buffer)
            buffer = part
        else:
            buffer = f"{buffer}{part}" if buffer else part

    if buffer:
        chunks.append(buffer)

    return chunks


def split_paragraphs(page_text: str) -> List[str]:
    """Split a page into paragraph-like units."""
    raw_blocks = re.split(r"\n\s*\n", page_text)
    paragraphs: List[str] = []

    for block in raw_blocks:
        block = normalize_text(block)
        if not block:
            continue
        paragraphs.extend(split_long_paragraph(block))

    if paragraphs:
        return paragraphs

    for line in page_text.splitlines():
        line = normalize_text(line)
        if line:
            paragraphs.extend(split_long_paragraph(line))

    return paragraphs


def chunk_paragraphs(
    paragraphs: List[str],
    target_chars: int = TARGET_CHARS,
    overlap_paragraphs: int = OVERLAP_PARAGRAPHS,
) -> List[str]:
    """Build paragraph chunks with simple overlap."""
    if not paragraphs:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_size = 0

    for paragraph in paragraphs:
        paragraph_size = len(paragraph)
        projected_size = current_size + paragraph_size + (2 if current else 0)

        if current and projected_size > target_chars:
            chunk_text = "\n\n".join(current).strip()
            if chunk_text:
                chunks.append(chunk_text)

            overlap = current[-overlap_paragraphs:] if overlap_paragraphs else []
            current = overlap.copy()
            current_size = sum(len(item) for item in current)

        current.append(paragraph)
        current_size += paragraph_size + (2 if len(current) > 1 else 0)

    if current:
        chunk_text = "\n\n".join(current).strip()
        if chunk_text:
            chunks.append(chunk_text)

    return chunks


def extract_chunks_from_pdf(pdf_path: Path) -> List[Dict[str, object]]:
    """Read the PDF page by page and return chunk records."""
    records: List[Dict[str, object]] = []

    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            page_text = page.get_text("text")
            paragraphs = split_paragraphs(page_text)
            chunks = chunk_paragraphs(paragraphs)

            for chunk_index, chunk_text in enumerate(chunks, start=1):
                chunk_id = f"{pdf_path.stem}-p{page_number}-c{chunk_index}"
                records.append(
                    {
                        "id": chunk_id,
                        "text": chunk_text,
                        "metadata": {
                            "page_number": page_number,
                            "chunk_id": chunk_id,
                            "source_file": pdf_path.name,
                            "text": chunk_text,
                        },
                    }
                )

    return records


def embed_texts(client: OpenAI, texts: List[str], batch_size: int = 50) -> List[List[float]]:
    """Create embeddings in batches to keep requests predictable."""
    embeddings: List[List[float]] = []
    embedding_model = get_embedding_model()

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            response = client.embeddings.create(model=embedding_model, input=batch)
        except AuthenticationError as exc:
            raise RuntimeError("OpenAI authentication failed. Please check OPENAI_API_KEY.") from exc
        except RateLimitError as exc:
            raise RuntimeError(
                "OpenAI quota was exceeded. Please use a key with available embedding quota."
            ) from exc
        except APIError as exc:
            raise RuntimeError(f"OpenAI API request failed: {exc}") from exc
        ordered_data = sorted(response.data, key=lambda item: item.index)
        embeddings.extend(item.embedding for item in ordered_data)

    return embeddings


def ensure_pdf_exists(pdf_path: Path) -> None:
    """Raise a helpful error when the expected PDF is missing."""
    if pdf_path.exists():
        return

    available = sorted(DATA_DIR.glob("*.pdf"))
    hint = ""
    if available:
        names = ", ".join(file.name for file in available)
        hint = f" Available PDFs in data/: {names}"

    raise FileNotFoundError(f"PDF not found: {pdf_path}.{hint}")


def ingest() -> None:
    """Embed the manual and store it in local ChromaDB."""
    load_dotenv()

    ensure_pdf_exists(PDF_PATH)

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    openai_client = OpenAI()
    chroma_client = chromadb.PersistentClient(path=str(DB_DIR))

    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    records = extract_chunks_from_pdf(PDF_PATH)
    if not records:
        raise ValueError("No text was extracted from the PDF.")

    texts = [record["text"] for record in records]
    embeddings = embed_texts(openai_client, texts)

    for start in range(0, len(records), 100):
        batch_records = records[start : start + 100]
        batch_embeddings = embeddings[start : start + 100]
        collection.upsert(
            ids=[record["id"] for record in batch_records],
            documents=[record["text"] for record in batch_records],
            metadatas=[record["metadata"] for record in batch_records],
            embeddings=batch_embeddings,
        )

    print(f"Ingested {len(records)} chunks from {PDF_PATH.name} into {DB_DIR}.")


if __name__ == "__main__":
    try:
        ingest()
    except Exception as exc:
        print(f"Failed to ingest PDF: {exc}")
        raise
