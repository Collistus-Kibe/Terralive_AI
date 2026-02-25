"""
RAG Engine — Vertex AI embeddings + Elasticsearch vector search.

Provides embedding generation and KNN search against the `agri_manuals`
index for the Gemini Live agent to retrieve crop-disease treatments and
agricultural best practices.
"""

import asyncio

from elasticsearch import Elasticsearch
import vertexai
from vertexai.language_models import TextEmbeddingModel

from core.config import settings

# ── Elasticsearch client (lazy) ──────────────────────────────
_es_client = None


def _get_es_client() -> Elasticsearch:
    """Return the ES client, creating it on first call."""
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(
            settings.ELASTIC_URL,
            api_key=settings.ELASTIC_API_KEY,
        )
    return _es_client

# ── Constants ────────────────────────────────────────────────
_INDEX_NAME = "agri_manuals"
_EMBEDDING_MODEL_NAME = "text-embedding-004"
_EMBEDDING_DIMS = 768


async def init_vertex() -> None:
    """
    Initialise the Vertex AI SDK.
    Must be called once at server startup.
    """
    await asyncio.to_thread(
        vertexai.init, project="terralive-agent", location="us-central1"
    )
    print("[RAG] Vertex AI initialised.")


async def get_embedding(text: str) -> list[float]:
    """
    Generate a 768-dim embedding for *text* using Vertex AI's
    text-embedding-004 model.  Runs in a thread to avoid blocking
    the async event loop.
    """
    def _embed():
        model = TextEmbeddingModel.from_pretrained(_EMBEDDING_MODEL_NAME)
        embeddings = model.get_embeddings([text])
        return embeddings[0].values

    return await asyncio.to_thread(_embed)


async def search_agronomy_knowledge(query: str) -> str:
    """
    Embed *query*, then perform a KNN (approximate-nearest-neighbour)
    search on the ``agri_manuals`` Elasticsearch index.

    Returns a newline-separated string of the top 3 most relevant
    manual excerpts, ready to be injected into the Gemini context.
    """
    vector = await get_embedding(query)

    knn_body = {
        "field": "content_vector",
        "query_vector": vector,
        "k": 3,
        "num_candidates": 20,
    }

    def _search():
        return _get_es_client().search(
            index=_INDEX_NAME,
            knn=knn_body,
            source=["title", "content"],
        )

    response = await asyncio.to_thread(_search)
    hits = response.get("hits", {}).get("hits", [])

    if not hits:
        return "No relevant agricultural knowledge found for this query."

    excerpts = []
    for i, hit in enumerate(hits, start=1):
        src = hit["_source"]
        title = src.get("title", "Untitled")
        content = src.get("content", "")
        score = round(hit.get("_score", 0), 3)
        excerpts.append(f"[{i}] {title} (score: {score})\n{content}")

    return "\n\n".join(excerpts)
