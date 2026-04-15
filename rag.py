import os
from pathlib import Path
from typing import Dict, List

import chromadb
from dotenv import load_dotenv
from openai import APIError, AuthenticationError, OpenAI, RateLimitError


BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
COLLECTION_NAME = "pharma_manual"
def get_embedding_model() -> str:
    """Read the embedding model after environment variables are loaded."""
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def build_snippet(text: str, max_length: int = 220) -> str:
    """Create a short snippet for the result list."""
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def get_collection():
    """Open the local Chroma collection used by the app."""
    chroma_client = chromadb.PersistentClient(path=str(DB_DIR))
    return chroma_client.get_collection(COLLECTION_NAME)


def embed_query(question: str) -> List[float]:
    """Embed the user question with the same model used at ingest time."""
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    client = OpenAI()
    try:
        response = client.embeddings.create(model=get_embedding_model(), input=question)
    except AuthenticationError as exc:
        raise RuntimeError("OpenAI authentication failed. Please check OPENAI_API_KEY.") from exc
    except RateLimitError as exc:
        raise RuntimeError("OpenAI quota was exceeded. Please update your API billing or key.") from exc
    except APIError as exc:
        raise RuntimeError(f"OpenAI API request failed: {exc}") from exc
    return response.data[0].embedding


def search_manual(question: str, top_k: int = 5) -> List[Dict[str, object]]:
    """Return ranked chunks with page numbers and snippets."""
    question = question.strip()
    if not question:
        return []

    if not DB_DIR.exists():
        raise FileNotFoundError("Vector database not found. Please run ingest.py first.")

    query_embedding = embed_query(question)

    try:
        collection = get_collection()
    except Exception as exc:
        raise RuntimeError("Chroma collection is not ready. Please run ingest.py first.") from exc

    if collection.count() == 0:
        raise RuntimeError("Vector database is empty. Please run ingest.py successfully first.")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    ranked_results: List[Dict[str, object]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        distance = float(distance) if distance is not None else 1.0
        score = max(0.0, 1.0 - distance)
        ranked_results.append(
            {
                "score": score,
                "distance": distance,
                "text": document,
                "snippet": build_snippet(document),
                "page_number": int(metadata.get("page_number", 1)),
                "chunk_id": metadata.get("chunk_id", ""),
                "source_file": metadata.get("source_file", ""),
            }
        )

    return ranked_results


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Search the local pharma manual vector store.")
    parser.add_argument("question", help="Question to search")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to return")
    args = parser.parse_args()

    print(json.dumps(search_manual(args.question, top_k=args.top_k), ensure_ascii=False, indent=2))
