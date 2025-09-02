
import os
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = os.getenv("DB_PATH", "vectordb")
MODEL_NAME = os.getenv("MODEL_NAME", "intfloat/e5-base-v2")

app = FastAPI(title="ShopTalk Vector Search API")

# init vector db + model
client = chromadb.PersistentClient(path=DB_PATH)
coll = client.get_or_create_collection(name="products", metadata={"hnsw:space":"cosine"})
model = SentenceTransformer(MODEL_NAME)

class SearchHit(BaseModel):
    id: str
    title: Optional[str] = None
    url: Optional[str] = None
    price: Optional[float] = None
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchHit]

@app.get("/health")
def health():
    return {"ok": True, "count": coll.count()}

@app.get("/search", response_model=SearchResponse)
def search(q: str = Query(..., description="User query"), k: int = 10):
    # e5 expects "query: " prefix for best results (per model card)
    qtext = f"query: {q}"
    qvec = model.encode([qtext], normalize_embeddings=True)[0].tolist()

    out = coll.query(query_embeddings=[qvec], n_results=k, include=["metadatas","distances"])
    hits = []
    ids = out.get("ids", [[]])[0]
    dists = out.get("distances", [[]])[0]  # cosine distance-ish; lower is better
    metas = out.get("metadatas", [[]])[0]

    # Turn distances into a similarity-ish score (1 - distance) for readability
    for i in range(len(ids)):
        m = metas[i] or {}
        hits.append(SearchHit(
            id=ids[i],
            title=m.get("title"),
            url=m.get("url"),
            price=m.get("price"),
            score=max(0.0, 1.0 - float(dists[i]))
        ))
    return SearchResponse(query=q, results=hits)
