#!/usr/bin/env python3
"""
Migration script to upload ChromaDB data to Weaviate Cloud
"""
import os
import chromadb
import weaviate
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

def migrate_to_weaviate():
    # Initialize ChromaDB (local)
    chroma_client = chromadb.PersistentClient(path="vectordb")
    chroma_collection = chroma_client.get_collection("products")
    
    # Initialize Weaviate
    from weaviate.auth import AuthApiKey
    weaviate_client = weaviate.connect_to_weaviate_cloud(
        cluster_url=os.getenv("WEAVIATE_URL"),
        auth_credentials=AuthApiKey(api_key=os.getenv("WEAVIATE_API_KEY"))
    )
    
    # Initialize encoder
    encoder = SentenceTransformer("mananthakris/e5-base-ft-abo")
    
    # Create schema
    class_name = "Product"
    schema = {
        "class": class_name,
        "description": "Product information for search",
        "vectorizer": "none",  # We'll provide our own vectors
        "properties": [
            {
                "name": "title",
                "dataType": ["text"],
                "description": "Product title"
            },
            {
                "name": "text", 
                "dataType": ["text"],
                "description": "Product description"
            },
            {
                "name": "category",
                "dataType": ["text"],
                "description": "Product category"
            },
            {
                "name": "url",
                "dataType": ["text"],
                "description": "Product URL"
            },
            {
                "name": "image_url",
                "dataType": ["text"],
                "description": "Product image URL"
            }
        ]
    }
    
    # Delete existing schema if it exists
    try:
        weaviate_client.collections.delete(class_name)
        print(f"Deleted existing {class_name} class")
    except:
        pass
    
    # Create new schema
    weaviate_client.collections.create(
        name=class_name,
        properties=[
            weaviate.classes.config.Property(name="title", data_type=weaviate.classes.config.DataType.TEXT),
            weaviate.classes.config.Property(name="text", data_type=weaviate.classes.config.DataType.TEXT),
            weaviate.classes.config.Property(name="category", data_type=weaviate.classes.config.DataType.TEXT),
            weaviate.classes.config.Property(name="url", data_type=weaviate.classes.config.DataType.TEXT),
            weaviate.classes.config.Property(name="image_url", data_type=weaviate.classes.config.DataType.TEXT),
        ],
        vectorizer_config=weaviate.classes.config.Configure.Vectorizer.none()
    )
    print(f"Created {class_name} class")
    
    # Get all data from ChromaDB
    print("Fetching data from ChromaDB...")
    all_data = chroma_collection.get(include=["metadatas", "embeddings"])
    
    ids = all_data["ids"]
    metadatas = all_data["metadatas"]
    embeddings = all_data["embeddings"]
    
    print(f"Found {len(ids)} products to migrate")
    
    # Upload to Weaviate in batches
    batch_size = 100
    collection = weaviate_client.collections.get(class_name)
    
    with collection.batch.dynamic() as batch:
        for i, (doc_id, metadata, embedding) in enumerate(zip(ids, metadatas, embeddings)):
            # Prepare data object
            data_object = {
                "title": metadata.get("title", ""),
                "text": metadata.get("text", ""),
                "category": metadata.get("category", ""),
                "url": metadata.get("url", ""),
                "image_url": metadata.get("image_url", "")
            }
            
            # Add to batch (let Weaviate generate UUID)
            batch.add_object(
                properties=data_object,
                vector=embedding
            )
            
            if (i + 1) % batch_size == 0:
                print(f"Processed {i + 1}/{len(ids)} products")
    
    print(f"Migration complete! Uploaded {len(ids)} products to Weaviate")
    
    # Verify migration
    count = collection.aggregate.over_all(total_count=True).total_count
    print(f"Verification: {count} products in Weaviate")
    
    # Close connection
    weaviate_client.close()

if __name__ == "__main__":
    migrate_to_weaviate()
