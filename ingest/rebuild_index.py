#!/usr/bin/env python
"""
Rebuild ChromaDB from a Parquet file using a (fine-tuned) SentenceTransformers model.

Example:
  python scripts/rebuild_index.py \
    --parquet data/products_ft.parquet \
    --db-path vectordb \
    --collection products \
    --model your-username/e5-base-ft-abo \
    --id-col item_id \
    --title-col item_name \
    --url-col image_url \
    --text-col text_for_embed_aug \
    --batch 512 \
    --wipe
"""

import os
import argparse
import shutil
from pathlib import Path

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer


def parse_args():
    p = argparse.ArgumentParser()
    # IO
    p.add_argument("--parquet", required=True, help="Path to Parquet containing products")
    p.add_argument("--db-path", default="vectordb", help="Chroma persistent directory")
    p.add_argument("--collection", default="products", help="Chroma collection name")
    p.add_argument("--wipe", action="store_true", help="Remove db-path before rebuild")

    # Columns
    p.add_argument("--id-col", default="item_id", help="Unique ID column")
    p.add_argument("--title-col", default="item_name", help="Title column (for metadata.title)")
    p.add_argument("--url-col", default="image_url", help="URL column (for metadata.url)")
    p.add_argument("--text-col", default="text_for_embed_aug", help="Text column to embed & store")

    # Model & batching
    p.add_argument("--model", default="mananthakris/e5-base-ft-abo", help="HF model id or local path")
    p.add_argument("--batch", type=int, default=512, help="Embedding/upsert batch size")
    return p.parse_args()


def needs_e5_prefix(model_name: str) -> bool:
    """Return True if we should prepend 'passage: ' to docs for this model family."""
    name = model_name.lower()
    return ("e5" in name) or ("gte" in name)  # common convention; extend if you like


def main():
    args = parse_args()

    # Optional clean wipe
    db_dir = Path(args.db_path)
    if args.wipe and db_dir.exists():
        print(f"[rebuild] Wiping {db_dir} ...")
        shutil.rmtree(db_dir)

    print(f"[rebuild] Loading Parquet: {args.parquet}")
    df = pd.read_parquet(args.parquet)

    # Basic column checks
    required_cols = {args.id_col, args.title_col, args.url_col, args.text_col}
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Parquet: {missing}")

    # Drop duplicate IDs
    before = len(df)
    df = df.drop_duplicates(subset=[args.id_col], keep="first").reset_index(drop=True)
    print(f"[rebuild] Dropped duplicates: {before - len(df)} (kept {len(df)})")

    # Prepare Chroma
    client = chromadb.PersistentClient(path=str(db_dir))
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    coll = client.get_or_create_collection(name=args.collection, metadata={"hnsw:space": "cosine"})

    # Load encoder (supports private HF repos via HUGGINGFACE_HUB_TOKEN)
    # If your FT model is local, pass the local folder path to --model
    print(f"[rebuild] Loading encoder: {args.model}")
    # SentenceTransformers will pick up HUGGINGFACE_HUB_TOKEN env var automatically for private repos
    encoder = SentenceTransformer(args.model)

    ids = df[args.id_col].astype(str).tolist()
    titles = df[args.title_col].astype(str).tolist()
    urls = df[args.url_col].astype(str).tolist()
    texts = df[args.text_col].astype(str).tolist()

    # Build metadata objects (aligns with your UI expectations)
    metadatas = [
        {"title": t, "url": u, "text": x}
        for t, u, x in zip(titles, urls, texts)
    ]

    # Encode docs (prefix for e5-like models)
    if needs_e5_prefix(args.model):
        enc_docs = [f"passage: {t}" for t in texts]
    else:
        enc_docs = texts

    print(f"[rebuild] Encoding {len(enc_docs)} docs ...")
    embeddings = encoder.encode(
        enc_docs,
        batch_size=args.batch,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    # Upsert in batches
    B = args.batch
    total = len(df)
    print(f"[rebuild] Upserting to Chroma (collection='{args.collection}') ...")
    for i in range(0, total, B):
        sl_ids = ids[i:i+B]
        sl_docs = texts[i:i+B]
        sl_meta = metadatas[i:i+B]
        sl_embs = embeddings[i:i+B].tolist()

        coll.upsert(
            ids=sl_ids,
            embeddings=sl_embs,
            metadatas=sl_meta,
            documents=sl_docs,  # optional, handy for debug
        )
        print(f"[rebuild] Upserted {i + len(sl_ids)}/{total}")

    print(f"[rebuild] Done. Collection count = {coll.count()}")
    print(f"[rebuild] DB path: {db_dir.resolve()}")


if __name__ == "__main__":
    main()