import chromadb, shutil, tempfile
from sentence_transformers import SentenceTransformer

def test_embed_and_retrieve_tiny():
    tmp = tempfile.mkdtemp()
    try:
        client = chromadb.PersistentClient(path=tmp)
        coll = client.get_or_create_collection(name="tiny", metadata={"hnsw:space":"cosine"})

        docs = [
            {"id":"1","text":"red running shoes for men", "brand":"Nike"},
            {"id":"2","text":"black formal leather shoes", "brand":"Clarks"},
            {"id":"3","text":"blue trail running sneakers", "brand":"Salomon"},
        ]

        enc = SentenceTransformer("mananthakris/e5-base-ft-abo")
        embeddings = enc.encode([f"passage: {d['text']}" for d in docs], normalize_embeddings=True)

        coll.add(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            metadatas=[{"brand": d["brand"]} for d in docs],
            embeddings=embeddings.tolist(),
        )

        q = "red sneakers"
        qemb = enc.encode([f"query: {q}"], normalize_embeddings=True).tolist()
        res = coll.query(query_embeddings=qemb, n_results=2, include=["metadatas", "documents", "ids"])
        assert len(res["ids"][0]) == 2
        # Expect the red shoe to be in top-2
        flat_ids = res["ids"][0]
        assert "1" in flat_ids
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
