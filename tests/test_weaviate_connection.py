"""
Test Weaviate connection and basic functionality
"""
import os
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

def test_weaviate_connection(weaviate_credentials):
    """Test basic Weaviate cluster connection"""
    try:
        import weaviate
        from weaviate.auth import AuthApiKey
        
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=weaviate_credentials["url"],
            auth_credentials=AuthApiKey(api_key=weaviate_credentials["api_key"])
        )
        
        # Test connection by getting cluster info
        meta = client.get_meta()
        assert "version" in meta
        print(f"✅ Connected to Weaviate cluster version: {meta.get('version', 'Unknown')}")
        
        client.close()
        
    except ImportError:
        pytest.skip("Weaviate client not installed")
    except Exception as e:
        pytest.fail(f"Failed to connect to Weaviate: {e}")

def test_weaviate_collection_exists(weaviate_credentials):
    """Test if the Product collection exists in Weaviate"""
    try:
        import weaviate
        from weaviate.auth import AuthApiKey
        
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=weaviate_credentials["url"],
            auth_credentials=AuthApiKey(api_key=weaviate_credentials["api_key"])
        )
        
        # Check if collection exists
        collections = client.collections.list_all()
        collection_names = list(collections.keys())
        
        assert weaviate_credentials["class_name"] in collection_names, \
            f"Collection '{weaviate_credentials['class_name']}' not found. Available: {collection_names}"
        
        print(f"✅ Collection '{weaviate_credentials['class_name']}' exists")
        
        client.close()
        
    except ImportError:
        pytest.skip("Weaviate client not installed")
    except Exception as e:
        pytest.fail(f"Failed to check collection: {e}")

def test_weaviate_data_count(weaviate_credentials):
    """Test if Weaviate has the expected number of products"""
    try:
        import weaviate
        from weaviate.auth import AuthApiKey
        
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=weaviate_credentials["url"],
            auth_credentials=AuthApiKey(api_key=weaviate_credentials["api_key"])
        )
        
        collection = client.collections.get(weaviate_credentials["class_name"])
        count = collection.aggregate.over_all(total_count=True).total_count
        
        # Should have migrated 145,615 products
        assert count > 0, "No products found in Weaviate"
        assert count >= 145000, f"Expected at least 145,000 products, found {count}"
        
        print(f"✅ Weaviate contains {count} products")
        
        client.close()
        
    except ImportError:
        pytest.skip("Weaviate client not installed")
    except Exception as e:
        pytest.fail(f"Failed to count products: {e}")

def test_weaviate_search_functionality(weaviate_credentials):
    """Test basic search functionality in Weaviate"""
    try:
        import weaviate
        from weaviate.auth import AuthApiKey
        from sentence_transformers import SentenceTransformer
        
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=weaviate_credentials["url"],
            auth_credentials=AuthApiKey(api_key=weaviate_credentials["api_key"])
        )
        
        # Initialize encoder
        encoder = SentenceTransformer("mananthakris/e5-base-ft-abo")
        
        # Test search
        query = "red running shoes"
        query_embedding = encoder.encode([f"query: {query}"], normalize_embeddings=True)[0].tolist()
        
        collection = client.collections.get(weaviate_credentials["class_name"])
        results = collection.query.near_vector(
            near_vector=query_embedding,
            limit=5,
            return_metadata=["distance"]
        )
        
        assert len(results.objects) > 0, "No search results returned"
        assert len(results.objects) <= 5, "Too many results returned"
        
        # Check result structure
        first_result = results.objects[0]
        assert hasattr(first_result, 'properties'), "Result missing properties"
        assert hasattr(first_result, 'metadata'), "Result missing metadata"
        assert hasattr(first_result.metadata, 'distance'), "Result missing distance"
        
        print(f"✅ Search returned {len(results.objects)} results")
        print(f"   First result: {first_result.properties.get('title', 'No title')[:50]}...")
        print(f"   Distance: {first_result.metadata.distance:.3f}")
        
        client.close()
        
    except ImportError:
        pytest.skip("Weaviate client not installed")
    except Exception as e:
        pytest.fail(f"Failed to test search: {e}")

if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
