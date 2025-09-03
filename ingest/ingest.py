
import os
from pathlib import Path
import pandas as pd
import chromadb

DB_DIR = Path("vectordb")
DB_DIR.mkdir(exist_ok=True)

def main():
    df = pd.read_parquet("data/products_e5-base.parquet")
    before = len(df)
    df = df.drop_duplicates(subset=["item_id"], keep="first").reset_index(drop=True)
    print(f"Dropped duplicates: {before - len(df)} (kept {len(df)} rows)")
    client = chromadb.PersistentClient(path=str(DB_DIR))
    coll = client.get_or_create_collection(
        name="products",
        metadata={"hnsw:space": "cosine"}  # cosine similarity
    )

    # Upsert in chunks (Chroma can handle lists directly)
    B = 1000
    for i in range(0, len(df), B):
        sl = df.iloc[i:i+B]
        coll.upsert(
            ids=sl["item_id"].astype(str).tolist(),
            embeddings=sl["embedding"].tolist(),
            metadatas=[
                {
                    "title": sl.iloc[j]["item_name"],
                    "url": sl.iloc[j]["image_url"],
                    # "price": None if pd.isna(sl.iloc[j]["price"]) else float(sl.iloc[j]["price"]),
                    "text": sl.iloc[j]["text_for_embed_aug"]
                }
                for j in range(len(sl))
            ],
            documents=sl["text_for_embed_aug"].tolist(),  # optional
        )
        print(f"Upserted {i+len(sl)}/{len(df)}")

    print("Done. Chroma DB at", DB_DIR.resolve())

if __name__ == "__main__":
    main()
