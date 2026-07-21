import os
from datetime import datetime, timezone

from openai import OpenAI

_openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

SCORE_THRESHOLD = float(os.environ.get("MEMORY_SCORE_THRESHOLD", "0.75"))
TOP_K = int(os.environ.get("MEMORY_TOP_K", "5"))
VECTOR_INDEX_NAME = "vector_index"


def embed_text(text: str) -> list[float]:
    res = _openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return res.data[0].embedding


def store_memory(
    collection,
    admin_id: str,
    event_type: str,
    text: str,
    metadata: dict,
) -> None:
    embedding = embed_text(text)
    collection.insert_one({
        "admin_id": admin_id,
        "event_type": event_type,
        "text": text,
        "embedding": embedding,
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc),
    })


def retrieve_memories(collection, admin_id: str, query_text: str) -> list[str]:
    query_vec = embed_text(query_text)
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vec,
                "numCandidates": TOP_K * 10,
                "limit": TOP_K,
                "filter": {"admin_id": admin_id},
            }
        },
        {
            "$project": {
                "text": 1,
                "score": {"$meta": "vectorSearchScore"},
                "_id": 0,
            }
        },
    ]
    results = list(collection.aggregate(pipeline))
    return [r["text"] for r in results if r.get("score", 0) >= SCORE_THRESHOLD]
