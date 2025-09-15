# api/main.py (excerpt)
import os, json
import numpy as np
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer
from sentence_transformers import CrossEncoder

from llm_helper import llm_parse_query, llm_nlg_answer  # <-- new
from dotenv import load_dotenv

load_dotenv()
client = chromadb.PersistentClient(path=os.getenv("DB_PATH", "vectordb"))
coll   = client.get_or_create_collection(name="products", metadata={"hnsw:space":"cosine"})
encoder = SentenceTransformer(os.getenv("MODEL_NAME", "mananthakris/e5-base-ft-abo"))
# print("Encoder name:",os.getenv("MODEL_NAME"))
# print("Encoder dims:",encoder.get_sentence_embedding_dimension())
# query = "red running shoes under $100"
# doc   = "Category: shoes. Title: Nike Pegasus 40. A red running shoe ..."

# q1 = encoder.encode([f"query: {query}"], normalize_embeddings=True)[0]
# q2 = encoder.encode([query], normalize_embeddings=True)[0]
# p1 = encoder.encode([f"passage: {doc}"], normalize_embeddings=True)[0]
# p2 = encoder.encode([doc], normalize_embeddings=True)[0]

# def cos(a,b): return float(np.dot(a,b))

# print("query:, passage:  ->", cos(q1,p1))
# print("query:, plain     ->", cos(q1,p2))
# print("plain,  passage:  ->", cos(q2,p1))
# print("plain,  plain     ->", cos(q2,p2))

app = FastAPI(title="ShopTalk — LLM + Vector Search")
reranker = CrossEncoder("BAAI/bge-reranker-v2-m3") # good multilingual reranker

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
    fcat   = norm(filters.get("category"))
    must   = [norm(t) for t in (filters.get("must_have") or []) if norm(t)]

    kept = []
    for idx, m in enumerate(metas):
        if not m: 
            continue
        ok = True
        blob = (m.get("title","") + " " + m.get("text","")).lower()

        # category - more precise matching to avoid false positives
        if fcat:
            db_cat = norm(m.get("category"))
            # Allow if: exact match, contains match, or category is in the text blob
            # Be more strict about word overlap to avoid false positives
            category_match = (
                fcat == db_cat or  # exact match
                fcat in db_cat or  # LLM category is in DB category
                db_cat in fcat or  # DB category is in LLM category
                fcat in blob       # LLM category is in product text
            )
            if not category_match:
                ok = False

        # price
        if pmax is not None and m.get("price") not in (None, ""):
            try:
                ok &= float(m["price"]) <= float(pmax)
            except:
                pass

        # color/brand/gender: structured or blob fallback (no synonyms)
        if fcolor and (fcolor not in norm(m.get("color")) and fcolor not in blob):
            ok = False
        if fbrand and (fbrand not in norm(m.get("brand")) and fbrand not in blob):
            ok = False
        if fgender and (fgender not in norm(m.get("gender")) and fgender not in blob):
            ok = False

        # NEW: LLM-provided must-have tokens (e.g., "running")
        if must and not all(tok in blob for tok in must):
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
    try:
        # Add timeout to prevent hanging
        async def search_with_timeout():
            # 1) LLM pre-search
            parsed = await llm_parse_query(q)
            rewritten = parsed.get("rewrite") or q
            print(f"filters: {parsed}")

            print(f"rewritten query: {rewritten}")
            # 2) Retrieve - let vector search handle category matching naturally
            pool = max(k * 2, 100)  # Get more results to allow for post-filtering
            qvec = embed_query(rewritten)
            out  = coll.query(query_embeddings=[qvec], n_results=pool, include=["metadatas","distances"])
            

            # 3) Filter
            out_f = apply_filters(out, parsed)
            ids   = out_f["ids"][0] if out_f.get("ids") else []
            metas = out_f["metadatas"][0] if out_f.get("metadatas") else []
            dists = out_f["distances"][0] if out_f.get("distances") else []
            
            # If no results after filtering, try without category filter
            if not ids and parsed.get("category"):
                print(f"No results with category filter '{parsed.get('category')}', trying without category filter...")
                # Remove category from filters and try again
                parsed_no_cat = parsed.copy()
                parsed_no_cat["category"] = None
                out_f = apply_filters(out, parsed_no_cat)
                ids   = out_f["ids"][0] if out_f.get("ids") else []
                metas = out_f["metadatas"][0] if out_f.get("metadatas") else []
                dists = out_f["distances"][0] if out_f.get("distances") else []
            
            #rerank BEFORE trimming to top-k
            if ids and metas:
                ids, metas, dists = rerank(rewritten, ids, metas, dists, topn=50)

            # slice down to final top-k
            ids, metas, dists = ids[:k], metas[:k], dists[:k]
            debug_distribution("post-filters", ids, metas)

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
        
        # Run with 30 second timeout
        result = await asyncio.wait_for(search_with_timeout(), timeout=30.0)
        return result
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Search request timed out. Please try a different query.")
    except Exception as e:
        print(f"Error in search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

def debug_distribution(label, ids, metas):
    import pandas as pd
    cats = [ (m.get("category") or "").lower() for m in metas ]
    print(f"{label} top-K category dist:\n", pd.Series(cats).value_counts().head(10))

def rerank(q: str, ids, metas, dists, topn: int = 50):
    n = min(topn, len(metas))
    pairs = [(q, (m.get("text") or m.get("title") or "")) for m in metas[:n]]
    scores = reranker.predict(pairs)  # array of floats
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    return [ids[i] for i in order], [metas[i] for i in order], [dists[i] for i in order]
