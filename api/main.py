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

try:
    from llm_helper import llm_parse_query, llm_nlg_answer  # Docker container
except ImportError:
    from api.llm_helper import llm_parse_query, llm_nlg_answer  # Local development
from dotenv import load_dotenv

load_dotenv()

# Global model cache to prevent repeated downloads
_model_cache = {}

def get_encoder():
    """Get encoder with caching and retry logic to handle rate limits"""
    model_name = os.getenv("MODEL_NAME", "mananthakris/e5-base-ft-abo")
    
    if model_name in _model_cache:
        return _model_cache[model_name]
    
    try:
        print(f"Loading model: {model_name}")
        encoder = SentenceTransformer(model_name)
        _model_cache[model_name] = encoder
        print(f"Model loaded successfully: {model_name}")
        return encoder
    except Exception as e:
        print(f"Error loading model {model_name}: {e}")
        # Fallback to the base e5 model if the fine-tuned one fails
        fallback_model = "intfloat/e5-base-v2"
        print(f"Falling back to: {fallback_model}")
        try:
            encoder = SentenceTransformer(fallback_model)
            _model_cache[fallback_model] = encoder
            return encoder
        except Exception as fallback_error:
            print(f"Fallback model also failed: {fallback_error}")
            raise

# Initialize encoder with error handling
encoder = get_encoder()

# Initialize vector database (Pinecone for cloud, ChromaDB for local)
try:
    from vector_db import VectorDB
    vectordb = VectorDB(encoder)
except ImportError:
    from api.vector_db import VectorDB
    vectordb = VectorDB(encoder)
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
    """Embed query with retry logic for rate limit handling"""
    import time
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return vectordb.embed_query(text)
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Rate limit exceeded after {max_retries} attempts")
                    raise
            else:
                raise

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

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": "2025-01-16T20:00:00Z"}

@app.get("/debug")
def debug():
    """Debug endpoint to check system status"""
    try:
        # Test vector database connection
        test_query = "test"
        qvec = embed_query(test_query)
        test_results = vectordb.query(query_embedding=qvec, n_results=1, include_metadata=True)
        
        return {
            "status": "healthy",
            "vectordb_connected": True,
            "vectordb_type": "Weaviate" if os.getenv("USE_WEAVIATE", "false").lower() == "true" else "ChromaDB",
            "total_products": vectordb.count(),
            "test_query_results": len(test_results.get("ids", [[]])[0]),
            "timestamp": "2025-01-16T20:00:00Z"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": "2025-01-16T20:00:00Z"
        }

@app.get("/answer", response_model=AnswerResp)
async def answer(q: str = Query(...), k: int = 20):
    try:
        # Add timeout to prevent hanging
        async def search_with_timeout():
            # 1) LLM pre-search (with timeout)
            try:
                parsed = await asyncio.wait_for(llm_parse_query(q), timeout=10.0)
            except asyncio.TimeoutError:
                print("LLM query parsing timed out, using basic parsing")
                parsed = {"rewrite": q, "category": None, "color": None, "brand": None, "gender": None, "price_max": None, "must_have": []}
            rewritten = parsed.get("rewrite") or q
            print(f"filters: {parsed}")

            print(f"rewritten query: {rewritten}")
            # 2) Retrieve - let vector search handle category matching naturally
            pool = max(k * 2, 100)  # Get more results to allow for post-filtering
            print(f"Starting vector search with pool size: {pool}")
            qvec = embed_query(rewritten)
            out  = vectordb.query(query_embedding=qvec, n_results=pool, include_metadata=True)
            print(f"Vector search completed, found {len(out.get('ids', [[]])[0])} results")
            

            # 3) Filter
            print("Starting filtering...")
            out_f = apply_filters(out, parsed)
            ids   = out_f["ids"][0] if out_f.get("ids") else []
            metas = out_f["metadatas"][0] if out_f.get("metadatas") else []
            dists = out_f["distances"][0] if out_f.get("distances") else []
            print(f"Filtering completed, {len(ids)} results after filtering")
            
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
            
            #rerank BEFORE trimming to top-k (limit to reasonable size for performance)
            if ids and metas:
                # Limit reranking to prevent timeouts with large result sets
                rerank_limit = min(50, len(metas), k * 3)  # Don't rerank more than 3x the requested k
                print(f"Reranking top {rerank_limit} results from {len(metas)} total")
                try:
                    # Add timeout for reranking to prevent hanging
                    async def rerank_with_timeout():
                        return rerank(rewritten, ids, metas, dists, topn=rerank_limit)
                    ids, metas, dists = await asyncio.wait_for(rerank_with_timeout(), timeout=10.0)
                    print("Reranking completed successfully")
                except asyncio.TimeoutError:
                    print("Reranking timed out, using original order")
                    # Keep original order if reranking times out
                    pass

            # slice down to final top-k BEFORE LLM processing
            ids, metas, dists = ids[:k], metas[:k], dists[:k]
            debug_distribution("post-filters", ids, metas)
            
            # 4) NLG over candidates (with timeout)
            # Use all results for LLM, but with optimized processing
            print(f"Starting LLM response generation for {len(metas)} products...")
            try:
                answer = await asyncio.wait_for(llm_nlg_answer(q, parsed, metas), timeout=25.0)
                print("LLM response generation completed")
            except asyncio.TimeoutError:
                print("LLM response generation timed out, using fallback response")
                answer = f"Found {len(metas)} products matching your search for '{q}'. Here are the top results:"

            # Convert distances → similarity-ish score for UI
            results = []
            for i, m, d in zip(ids, metas, dists):
                s = max(0.0, 1.0 - float(d))
                r = dict(m or {})
                r["id"] = r.get("id", i)
                r["score"] = s
                results.append(r)

            print(f"Returning {len(results)} results to UI")
            response = AnswerResp(answer=answer, rewritten_query=rewritten, filters=parsed, results=results)
            print(f"Response prepared successfully: answer length={len(answer)}, results count={len(results)}")
            return response
        
        # Run with 50 second timeout (increased for Weaviate + LLM operations with full result sets)
        result = await asyncio.wait_for(search_with_timeout(), timeout=50.0)
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
    # Optimize text extraction for reranking
    pairs = []
    for m in metas[:n]:
        text = m.get("text") or m.get("title") or ""
        # Truncate very long texts to improve reranking speed
        if len(text) > 500:
            text = text[:500] + "..."
        pairs.append((q, text))
    
    print(f"Reranking {len(pairs)} pairs...")
    scores = reranker.predict(pairs)  # array of floats
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    return [ids[i] for i in order], [metas[i] for i in order], [dists[i] for i in order]
