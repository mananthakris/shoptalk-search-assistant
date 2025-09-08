#!/usr/bin/env python
import argparse, shutil
from pathlib import Path
import pandas as pd
import numpy as np
import chromadb

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", required=True)
    p.add_argument("--db-path", default="vectordb")
    p.add_argument("--collection", default="products")
    p.add_argument("--wipe", action="store_true")
    p.add_argument("--id-col", default="item_id")
    p.add_argument("--title-col", default="item_name_c")
    p.add_argument("--url-col", default="image_url")
    p.add_argument("--text-col", default="text_for_embed_aug")
    p.add_argument("--ptype-col", default="product_type_c")   
    p.add_argument("--embedding-col", default="embedding")
    p.add_argument("--batch", type=int, default=1000)
    return p.parse_args()

def extract_category(v):
    # Handles dict/list/str; ABO often stores {"value":"SHOES"}
    if v is None: return ""
    if isinstance(v, dict):
        if "value" in v and v["value"]:
            return str(v["value"]).strip().lower()
        # join all values as fallback
        return " ".join(str(x) for x in v.values()).strip().lower()
    if isinstance(v, list):
        return " ".join(extract_category(x) for x in v).strip().lower()
    return str(v).strip().lower()

def main():
    args = parse_args()

    db_dir = Path(args.db_path)
    if args.wipe and db_dir.exists():
        print(f"[rebuild] Wiping {db_dir} ..."); shutil.rmtree(db_dir)

    print(f"[rebuild] Loading Parquet: {args.parquet}")
    df = pd.read_parquet(args.parquet)

    required = {args.id_col, args.title_col, args.url_col, args.text_col, args.embedding_col}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    before = len(df)
    df = df.drop_duplicates(subset=[args.id_col], keep="first").reset_index(drop=True)
    print(f"[rebuild] Dropped duplicates: {before - len(df)} (kept {len(df)})")

  
    E = np.vstack(df["embedding"].to_list()).astype("float32")
    norms = np.linalg.norm(E, axis=1)
    print("Doc vector norms: mean=", norms.mean(), "std=", norms.std(), "min=", norms.min(), "max=", norms.max())
    
    # If not ~1.0, normalize and save before upsert:
    if not (0.97 < norms.mean() < 1.03):
        E = E / np.clip(np.linalg.norm(E, axis=1, keepdims=True), 1e-8, None)
        df["embedding"] = [e.tolist() for e in E]

    # # Build category if present
    # if args.ptype_col in df.columns:
    #     df["_category"] = df[args.ptype_col].apply(extract_category)
    # else:
    #     df["_category"] = ""

    client = chromadb.PersistentClient(path=str(db_dir))
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    coll = client.get_or_create_collection(name=args.collection, metadata={"hnsw:space":"cosine"})

    ids   = df[args.id_col].astype(str).tolist()
    titles= df[args.title_col].astype(str).tolist()
    urls  = df[args.url_col].astype(str).tolist()
    texts = df[args.text_col].astype(str).tolist()
    embs  = df[args.embedding_col].tolist()
    cats  = df[args.ptype_col].astype(str).tolist()

    metadatas = [
        {"title": t, "url": u, "text": x, "category": c}
        for t, u, x, c in zip(titles, urls, texts, cats)
    ]

    B = args.batch
    total = len(df)
    print(f"[rebuild] Upserting {total} rows into '{args.collection}' ...")
    for i in range(0, total, B):
        coll.upsert(
            ids=ids[i:i+B],
            embeddings=embs[i:i+B],
            metadatas=metadatas[i:i+B],
            documents=texts[i:i+B],
        )
        print(f"[rebuild] Upserted {min(i+B, total)}/{total}")

    print(f"[rebuild] Done. Count = {coll.count()} | DB: {db_dir.resolve()}")

if __name__ == "__main__":
    main()