"""
Test VectorDB abstraction layer functionality
"""
import os
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@pytest.fixture
def encoder():
    """Initialize sentence transformer encoder"""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("mananthakris/e5-base-ft-abo")
    except ImportError:
        pytest.skip("Sentence transformers not installed")

@pytest.fixture
def weaviate_credentials():
    """Check if Weaviate credentials are available"""
    url = os.getenv("WEAVIATE_URL")
    api_key = os.getenv("WEAVIATE_API_KEY")
    class_name = os.getenv("WEAVIATE_CLASS_NAME", "Product")
    
    if not url or not api_key:
        pytest.skip("Weaviate credentials not found in environment")
    
    return {
        "url": url,
        "api_key": api_key,
        "class_name": class_name
    }

def test_vector_db_chromadb_initialization(encoder):
    """Test VectorDB initialization with ChromaDB (local)"""
    try:
        from api.vector_db import VectorDB
        
        # Ensure we're using ChromaDB
        os.environ.pop("USE_WEAVIATE", None)
        
        vectordb = VectorDB(encoder)
        
        # Should be using ChromaDB
        assert not vectordb.use_weaviate
        assert hasattr(vectordb, 'collection')
        assert vectordb.collection is not None
        
        print("✅ VectorDB initialized with ChromaDB")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to initialize VectorDB with ChromaDB: {e}")

def test_vector_db_weaviate_initialization(encoder, weaviate_credentials):
    """Test VectorDB initialization with Weaviate (cloud)"""
    try:
        from api.vector_db import VectorDB
        
        # Set environment to use Weaviate
        os.environ["USE_WEAVIATE"] = "true"
        
        vectordb = VectorDB(encoder)
        
        # Should be using Weaviate
        assert vectordb.use_weaviate
        assert hasattr(vectordb, 'client')
        assert vectordb.client is not None
        assert vectordb.class_name == weaviate_credentials["class_name"]
        
        print("✅ VectorDB initialized with Weaviate")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to initialize VectorDB with Weaviate: {e}")

def test_embed_query_functionality(encoder):
    """Test query embedding generation"""
    try:
        from api.vector_db import VectorDB
        
        # Use ChromaDB for this test (simpler setup)
        os.environ.pop("USE_WEAVIATE", None)
        
        vectordb = VectorDB(encoder)
        
        # Test query embedding
        query = "red running shoes"
        embedding = vectordb.embed_query(query)
        
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)
        
        print(f"✅ Generated embedding of length {len(embedding)} for query: '{query}'")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to generate query embedding: {e}")

def test_embed_documents_functionality(encoder):
    """Test document embedding generation"""
    try:
        from api.vector_db import VectorDB
        
        # Use ChromaDB for this test
        os.environ.pop("USE_WEAVIATE", None)
        
        vectordb = VectorDB(encoder)
        
        # Test document embeddings
        documents = [
            "This is a red running shoe for athletes",
            "A comfortable walking shoe for daily use"
        ]
        embeddings = vectordb.embed_documents(documents)
        
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(documents)
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) > 0 for emb in embeddings)
        
        print(f"✅ Generated {len(embeddings)} document embeddings")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to generate document embeddings: {e}")

def test_chromadb_query_functionality(encoder):
    """Test ChromaDB query functionality"""
    try:
        from api.vector_db import VectorDB
        
        # Use ChromaDB
        os.environ.pop("USE_WEAVIATE", None)
        
        vectordb = VectorDB(encoder)
        
        # Test query
        query = "red running shoes"
        query_embedding = vectordb.embed_query(query)
        
        results = vectordb.query(
            query_embedding=query_embedding,
            n_results=5,
            include_metadata=True
        )
        
        # Check result structure (ChromaDB format)
        assert "ids" in results
        assert "distances" in results
        assert "metadatas" in results
        
        assert isinstance(results["ids"], list)
        assert len(results["ids"]) > 0
        assert len(results["ids"][0]) > 0  # Should have at least one result
        
        print(f"✅ ChromaDB query returned {len(results['ids'][0])} results")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to query ChromaDB: {e}")

def test_weaviate_query_functionality(encoder, weaviate_credentials):
    """Test Weaviate query functionality"""
    try:
        from api.vector_db import VectorDB
        
        # Use Weaviate
        os.environ["USE_WEAVIATE"] = "true"
        
        vectordb = VectorDB(encoder)
        
        # Test query
        query = "red running shoes"
        query_embedding = vectordb.embed_query(query)
        
        results = vectordb.query(
            query_embedding=query_embedding,
            n_results=5,
            include_metadata=True
        )
        
        # Check result structure (should match ChromaDB format)
        assert "ids" in results
        assert "distances" in results
        assert "metadatas" in results
        
        assert isinstance(results["ids"], list)
        assert len(results["ids"]) > 0
        assert len(results["ids"][0]) > 0  # Should have at least one result
        
        print(f"✅ Weaviate query returned {len(results['ids'][0])} results")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to query Weaviate: {e}")

def test_count_functionality(encoder):
    """Test count functionality for both databases"""
    try:
        from api.vector_db import VectorDB
        
        # Test ChromaDB count
        os.environ.pop("USE_WEAVIATE", None)
        vectordb_chroma = VectorDB(encoder)
        chroma_count = vectordb_chroma.count()
        
        assert isinstance(chroma_count, int)
        assert chroma_count > 0
        
        print(f"✅ ChromaDB count: {chroma_count}")
        
        # Test Weaviate count if credentials available
        if os.getenv("WEAVIATE_URL") and os.getenv("WEAVIATE_API_KEY"):
            os.environ["USE_WEAVIATE"] = "true"
            vectordb_weaviate = VectorDB(encoder)
            weaviate_count = vectordb_weaviate.count()
            
            assert isinstance(weaviate_count, int)
            assert weaviate_count > 0
            
            print(f"✅ Weaviate count: {weaviate_count}")
            
            # Both should have similar counts (migrated data)
            assert abs(chroma_count - weaviate_count) < 1000, \
                f"Count mismatch: ChromaDB={chroma_count}, Weaviate={weaviate_count}"
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to test count functionality: {e}")

def test_result_format_compatibility(encoder, weaviate_credentials):
    """Test that both databases return compatible result formats"""
    try:
        from api.vector_db import VectorDB
        
        query = "red running shoes"
        
        # Test ChromaDB
        os.environ.pop("USE_WEAVIATE", None)
        vectordb_chroma = VectorDB(encoder)
        query_embedding = vectordb_chroma.embed_query(query)
        
        chroma_results = vectordb_chroma.query(
            query_embedding=query_embedding,
            n_results=3,
            include_metadata=True
        )
        
        # Test Weaviate
        os.environ["USE_WEAVIATE"] = "true"
        vectordb_weaviate = VectorDB(encoder)
        
        weaviate_results = vectordb_weaviate.query(
            query_embedding=query_embedding,
            n_results=3,
            include_metadata=True
        )
        
        # Both should have the same structure
        for key in ["ids", "distances", "metadatas"]:
            assert key in chroma_results
            assert key in weaviate_results
            
            assert isinstance(chroma_results[key], list)
            assert isinstance(weaviate_results[key], list)
            
            assert len(chroma_results[key]) > 0
            assert len(weaviate_results[key]) > 0
        
        print("✅ Result formats are compatible between ChromaDB and Weaviate")
        
    except ImportError as e:
        pytest.skip(f"Required dependencies not available: {e}")
    except Exception as e:
        pytest.fail(f"Failed to test result format compatibility: {e}")

if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
