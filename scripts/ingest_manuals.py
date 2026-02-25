"""
Ingestion script — seed the `agri_manuals` Elasticsearch index with
real-world agricultural advice so the RAG pipeline can retrieve it.

Usage:
    python -m scripts.ingest_manuals
"""

import asyncio
import sys
import os

# Ensure the project root is on the path so `services.*` imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.rag_engine import (
    _get_es_client,
    get_embedding,
    init_vertex,
    _INDEX_NAME,
    _EMBEDDING_DIMS,
)

# ── Sample agricultural knowledge base ───────────────────────
MANUALS = [
    {
        "title": "Maize Chlorotic Mottle Virus (MCMV)",
        "content": (
            "MCMV causes yellowing of leaves and stunted growth. "
            "Transmitted by thrips. Treatment involves crop rotation "
            "and applying systemic insecticides like Imidacloprid "
            "early in the season."
        ),
    },
    {
        "title": "Coffee Berry Disease",
        "content": (
            "Fungal infection causing dark sunken lesions on green "
            "berries. Thrives in high humidity. Control using "
            "Copper-based fungicides before the onset of long rains."
        ),
    },
    {
        "title": "Optimal Nitrogen Application for Tea",
        "content": (
            "Apply NPK fertilizer in splits. First split at the "
            "beginning of the rainy season to maximize leaf flush. "
            "Ensure soil pH is between 5.0 and 5.6."
        ),
    },
    {
        "title": "Fall Armyworm Management in Maize",
        "content": (
            "Fall armyworm is identified by an inverted Y on the "
            "head capsule. Early scouting is critical. Apply "
            "Emamectin Benzoate or Spinetoram when larvae are "
            "small (L1-L3). Integrate with push-pull technology "
            "using Desmodium and Brachiaria border rows."
        ),
    },
    {
        "title": "Tomato Late Blight (Phytophthora infestans)",
        "content": (
            "Water-soaked lesions on leaves that turn brown and "
            "papery. Spreads rapidly in cool wet conditions. "
            "Preventive sprays of Mancozeb or Ridomil Gold every "
            "7-10 days. Remove and destroy infected plants."
        ),
    },
    {
        "title": "Banana Xanthomonas Wilt (BXW)",
        "content": (
            "Bacterial wilt causing premature ripening and yellowing "
            "of leaves. No chemical cure exists. Control by removing "
            "the male bud with a forked stick after the last hand "
            "forms, sterilising tools between plants, and using "
            "clean planting materials."
        ),
    },
    {
        "title": "Soil pH Correction for Acidic Soils",
        "content": (
            "Apply agricultural lime (CaCO3) at 2-4 tonnes per "
            "hectare for soils below pH 5.0. Incorporate lime into "
            "the top 15 cm. Re-test after 3 months. Dolomitic lime "
            "also supplies magnesium."
        ),
    },
    {
        "title": "Drip Irrigation Scheduling for Vegetables",
        "content": (
            "Schedule irrigation based on crop ET (evapotranspiration). "
            "For tomatoes, apply 4-6 litres per plant per day during "
            "flowering and fruiting stages. Use tensiometers to "
            "monitor soil moisture tension — irrigate when readings "
            "exceed 30 kPa at 20 cm depth."
        ),
    },
]


async def setup_index() -> None:
    """
    Create the ``agri_manuals`` index with the correct mappings for
    dense_vector KNN search.  Deletes any existing index first.
    """
    if _get_es_client().indices.exists(index=_INDEX_NAME):
        _get_es_client().indices.delete(index=_INDEX_NAME)
        print(f"[Ingest] Deleted existing index '{_INDEX_NAME}'.")

    mappings = {
        "properties": {
            "title": {"type": "text"},
            "content": {"type": "text"},
            "content_vector": {
                "type": "dense_vector",
                "dims": _EMBEDDING_DIMS,
                "index": True,
                "similarity": "cosine",
            },
        }
    }

    _get_es_client().indices.create(index=_INDEX_NAME, mappings=mappings)
    print(f"[Ingest] Created index '{_INDEX_NAME}' (dims={_EMBEDDING_DIMS}).")


async def ingest_data() -> None:
    """
    Iterate through the sample manuals, generate embeddings, and
    index each document into Elasticsearch.
    """
    for i, doc in enumerate(MANUALS, start=1):
        print(f"[Ingest] Embedding {i}/{len(MANUALS)}: {doc['title']}...")
        vector = await get_embedding(doc["content"])

        body = {
            "title": doc["title"],
            "content": doc["content"],
            "content_vector": vector,
        }
        _get_es_client().index(index=_INDEX_NAME, id=str(i), document=body)
        print(f"[Ingest]   → indexed (vector length: {len(vector)})")

    # Refresh so documents are immediately searchable
    _get_es_client().indices.refresh(index=_INDEX_NAME)
    print(f"[Ingest] Done — {len(MANUALS)} documents ingested.")


async def main() -> None:
    await init_vertex()
    await setup_index()
    await ingest_data()


if __name__ == "__main__":
    asyncio.run(main())
