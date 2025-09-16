"""
Vector database abstraction layer supporting both ChromaDB (local) and Weaviate (cloud)
"""
import os
from typing import List, Dict, Any, Optional
import chromadb
from sentence_transformers import SentenceTransformer

# Try to import Weaviate, fall back to ChromaDB if not available
try:
    import weaviate
    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False

class VectorDB:
    def __init__(self, encoder: SentenceTransformer):
        self.encoder = encoder
        self.use_weaviate = os.getenv("USE_WEAVIATE", "false").lower() == "true"
        
        if self.use_weaviate and WEAVIATE_AVAILABLE:
            self._init_weaviate()
        else:
            self._init_chromadb()
    
    def _init_weaviate(self):
        """Initialize Weaviate connection"""
        from weaviate.auth import AuthApiKey
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url=os.getenv("WEAVIATE_URL"),
            auth_credentials=AuthApiKey(api_key=os.getenv("WEAVIATE_API_KEY"))
        )
        self.class_name = os.getenv("WEAVIATE_CLASS_NAME", "Product")
        print("Using Weaviate vector database")
    
    def _init_chromadb(self):
        """Initialize ChromaDB connection"""
        self.client = chromadb.PersistentClient(path=os.getenv("DB_PATH", "vectordb"))
        self.collection = self.client.get_or_create_collection(
            name="products", 
            metadata={"hnsw:space": "cosine"}
        )
        print("Using ChromaDB vector database (local)")
    
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a query"""
        return self.encoder.encode([f"query: {query}"], normalize_embeddings=True)[0].tolist()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for documents"""
        return self.encoder.encode([f"passage: {text}" for text in texts], normalize_embeddings=True).tolist()
    
    def query(self, query_embedding: List[float], n_results: int = 20, 
              include_metadata: bool = True) -> Dict[str, Any]:
        """Query the vector database"""
        if self.use_weaviate and WEAVIATE_AVAILABLE:
            return self._query_weaviate(query_embedding, n_results, include_metadata)
        else:
            return self._query_chromadb(query_embedding, n_results, include_metadata)
    
    def _query_weaviate(self, query_embedding: List[float], n_results: int, 
                       include_metadata: bool) -> Dict[str, Any]:
        """Query Weaviate"""
        try:
            collection = self.client.collections.get(self.class_name)
            results = collection.query.near_vector(
                near_vector=query_embedding,
                limit=n_results,
                return_metadata=["distance"]
            )
            
            # Convert Weaviate v4 format to ChromaDB format for compatibility
            if results.objects:
                return {
                    "ids": [[str(obj.uuid) for obj in results.objects]],
                    "distances": [[obj.metadata.distance for obj in results.objects]],
                    "metadatas": [[obj.properties for obj in results.objects]] if include_metadata else [[]]
                }
            else:
                return {"ids": [[]], "distances": [[]], "metadatas": [[]]}
        except Exception as e:
            print(f"Weaviate query error: {e}")
            return {"ids": [[]], "distances": [[]], "metadatas": [[]]}
    
    def _query_chromadb(self, query_embedding: List[float], n_results: int, 
                       include_metadata: bool) -> Dict[str, Any]:
        """Query ChromaDB"""
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["metadatas", "distances"] if include_metadata else ["distances"]
        )
    
    def count(self) -> int:
        """Get total number of documents"""
        if self.use_weaviate and WEAVIATE_AVAILABLE:
            try:
                collection = self.client.collections.get(self.class_name)
                return collection.aggregate.over_all(total_count=True).total_count
            except:
                return 0
        else:
            return self.collection.count()
    
    def add_documents(self, ids: List[str], embeddings: List[List[float]], 
                     metadatas: List[Dict[str, Any]]):
        """Add documents to the vector database"""
        if self.use_weaviate and WEAVIATE_AVAILABLE:
            self._add_to_weaviate(ids, embeddings, metadatas)
        else:
            self._add_to_chromadb(ids, embeddings, metadatas)
    
    def _add_to_weaviate(self, ids: List[str], embeddings: List[List[float]], 
                        metadatas: List[Dict[str, Any]]):
        """Add documents to Weaviate"""
        try:
            collection = self.client.collections.get(self.class_name)
            with collection.batch.dynamic() as batch:
                for doc_id, embedding, metadata in zip(ids, embeddings, metadatas):
                    batch.add_object(
                        properties=metadata,
                        uuid=doc_id,
                        vector=embedding
                    )
        except Exception as e:
            print(f"Weaviate add error: {e}")
    
    def _add_to_chromadb(self, ids: List[str], embeddings: List[List[float]], 
                        metadatas: List[Dict[str, Any]]):
        """Add documents to ChromaDB"""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )
