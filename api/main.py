# api/main.py (excerpt)
import os, json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer

from api.llm_helper import llm_parse_query, llm_nlg_answer  # <-- new

client = chromadb.PersistentClient(path=os.getenv("DB_PATH", "vectordb"))
coll   = client.get_or_create_collection(name="products", metadata={"hnsw:space":"cosine"})
encoder = SentenceTransformer(os.getenv("MODEL_NAME", "intfloat/e5-base-v2"))

app = FastAPI(title="ShopTalk — LLM + Vector Search")

def embed_query(text: str) -> List[float]:
    return encoder.encode([f"query: {text}"], normalize_embeddings=True)[0].tolist()

def apply_filters(results: Dict[str, List], filters: Dict[str, Any]) -> Dict[str, List]:
    ids   = results.get("ids", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    if not ids: return results

    def norm(x): return (x or "").strip().lower()
    pmax   = filters.get("price_max")
    fcolor = norm(filters.get("color"))
    fbrand = norm(filters.get("brand"))
    fgender= norm(filters.get("gender"))

    kept = []
    for idx, m in enumerate(metas):
        if not m: 
            continue
        ok = True
        if pmax is not None and m.get("price") not in (None, ""):
            try: ok &= float(m["price"]) <= float(pmax)
            except: pass
        if fcolor and norm(m.get("color")) not in ("", fcolor):
            ok = False
        if fbrand and fbrand not in norm(m.get("brand","")):
            ok = False
        if fgender and fgender not in norm(m.get("gender","")):
            ok = False
        if ok:
            kept.append((ids[idx], m, dists[idx]))

    if not kept:
        return results
    kept_ids, kept_metas, kept_dists = zip(*kept)
    return {"ids":[list(kept_ids)], "metadatas":[list(kept_metas)], "distances":[list(kept_dists)]}

class AnswerResp(BaseModel):
    answer: str
    rewritten_query: Optional[str] = None
    filters: Dict[str, Any]
    results: List[Dict[str, Any]]

@app.get("/answer", response_model=AnswerResp)
async def answer(q: str = Query(...), k: int = 20):
    # 1) LLM pre-search
    parsed = await llm_parse_query(q)
    rewritten = parsed.get("rewrite") or q

    # 2) Retrieve
    qvec = embed_query(rewritten)
    out  = coll.query(query_embeddings=[qvec], n_results=k, include=["metadatas","distances"])

    # 3) Filter
    out_f = apply_filters(out, parsed)
    ids   = out_f["ids"][0] if out_f.get("ids") else []
    metas = out_f["metadatas"][0] if out_f.get("metadatas") else []
    dists = out_f["distances"][0] if out_f.get("distances") else []

    # 4) NLG over candidates
    answer = await llm_nlg_answer(q, parsed, metas)

    # Convert distances → similarity-ish score for UI
    results = []
    for i, m, d in zip(ids, metas, dists):
        s = max(0.0, 1.0 - float(d))
        r = dict(m or {})
        r["id"] = r.get("id", i)
        r["score"] = s
        results.append(r)

    return AnswerResp(answer=answer, rewritten_query=rewritten, filters=parsed, results=results)