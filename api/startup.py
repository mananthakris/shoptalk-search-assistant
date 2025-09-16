#!/usr/bin/env python3
"""
Startup script to preload models and handle rate limits gracefully
"""
import os
import time
import sys
from sentence_transformers import SentenceTransformer
from sentence_transformers import CrossEncoder

def preload_models():
    """Preload models with retry logic"""
    print("🚀 Starting model preloading...")
    
    # Preload encoder
    model_name = os.getenv("MODEL_NAME", "mananthakris/e5-base-ft-abo")
    print(f"📥 Loading encoder: {model_name}")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            encoder = SentenceTransformer(model_name)
            print(f"✅ Encoder loaded successfully: {model_name}")
            break
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⚠️  Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Rate limit exceeded, falling back to default model")
                    encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                    print("✅ Fallback encoder loaded")
                    break
            else:
                print(f"❌ Error loading {model_name}: {e}")
                print("🔄 Falling back to default model")
                encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                print("✅ Fallback encoder loaded")
                break
    
    # Preload reranker
    print("📥 Loading reranker...")
    try:
        reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
        print("✅ Reranker loaded successfully")
    except Exception as e:
        print(f"❌ Error loading reranker: {e}")
        sys.exit(1)
    
    print("🎉 All models preloaded successfully!")
    return encoder, reranker

if __name__ == "__main__":
    preload_models()
