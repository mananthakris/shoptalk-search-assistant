"""
Test data migration from ChromaDB to Weaviate
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

@pytest.fixture
def chromadb_available():
    """Check if ChromaDB is available locally"""
    try:
        import chromadb
        # Check if local vectordb exists
        if os.path.exists("vectordb"):
            return True
        return False
    except ImportError:
        return False

def test_chromadb_data_availability(chromadb_available):
    """Test if ChromaDB data is available for migration"""
    if not chromadb_available:
        pytest.skip("ChromaDB not available or no local data found")
    
    try:
        import chromadb
        
        client = chromadb.PersistentClient(path="vectordb")
        collection = client.get_collection("products")
        count = collection.count()
        
        assert count > 0, "No data found in ChromaDB"
        assert count >= 145000, f"Expected at least 145,000 products, found {count}"
        
        print(f"✅ ChromaDB contains {count} products ready for migration")
        
    except Exception as e:
        pytest.fail(f"Failed to check ChromaDB data: {e}")

def test_weaviate_schema_creation(weaviate_credentials):
    """Test Weaviate schema creation"""
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
            f"Collection '{weaviate_credentials['class_name']}' not found"
        
        # Get collection and check properties
        collection = client.collections.get(weaviate_credentials["class_name"])
        config = collection.config.get()
        
        # Check if required properties exist
        property_names = [prop.name for prop in config.properties]
        required_properties = ["title", "text", "category", "url", "image_url"]
        
        for prop in required_properties:
            assert prop in property_names, f"Required property '{prop}' not found in schema"
        
        print(f"✅ Weaviate schema is properly configured with properties: {property_names}")
        
        client.close()
        
    except ImportError:
        pytest.skip("Weaviate client not installed")
    except Exception as e:
        pytest.fail(f"Failed to check Weaviate schema: {e}")

def test_migration_data_integrity(weaviate_credentials, chromadb_available):
    """Test that migrated data maintains integrity"""
    if not chromadb_available:
        pytest.skip("ChromaDB not available for comparison")
    
    try:
        import chromadb
        import weaviate
        from weaviate.auth import AuthApiKey
        from sentence_transformers import SentenceTransformer
        
        # Get ChromaDB data
        chroma_client = chromadb.PersistentClient(path="vectordb")
        chroma_collection = chroma_client.get_collection("products")
        chroma_count = chroma_collection.count()
        
        # Get Weaviate data
        weaviate_client = weaviate.connect_to_weaviate_cloud(
            cluster_url=weaviate_credentials["url"],
            auth_credentials=AuthApiKey(api_key=weaviate_credentials["api_key"])
        )
        
        weaviate_collection = weaviate_client.collections.get(weaviate_credentials["class_name"])
        weaviate_count = weaviate_collection.aggregate.over_all(total_count=True).total_count
        
        # Counts should be similar (allowing for small differences)
        assert abs(chroma_count - weaviate_count) < 1000, \
            f"Count mismatch: ChromaDB={chroma_count}, Weaviate={weaviate_count}"
        
        print(f"✅ Data integrity maintained: ChromaDB={chroma_count}, Weaviate={weaviate_count}")
        
        # Test a sample query to ensure data quality
        encoder = SentenceTransformer("mananthakris/e5-base-ft-abo")
        query = "red running shoes"
        query_embedding = encoder.encode([f"query: {query}"], normalize_embeddings=True)[0].tolist()
        
        # Query both databases
        chroma_results = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=3,
            include=["metadatas"]
        )
        
        weaviate_results = weaviate_collection.query.near_vector(
            near_vector=query_embedding,
            limit=3
        )
        
        # Both should return results
        assert len(chroma_results["ids"][0]) > 0, "ChromaDB returned no results"
        assert len(weaviate_results.objects) > 0, "Weaviate returned no results"
        
        print(f"✅ Both databases return results for test query: '{query}'")
        
        weaviate_client.close()
        
    except ImportError:
        pytest.skip("Required dependencies not installed")
    except Exception as e:
        pytest.fail(f"Failed to test data integrity: {e}")

def test_migration_script_functionality():
    """Test that the migration script can be imported and has required functions"""
    try:
        # Test if migration script exists and can be imported
        import sys
        import os
        
        # Add current directory to path if needed
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        
        # Try to import the migration script
        import migrate_to_weaviate
        
        # Check if the main function exists
        assert hasattr(migrate_to_weaviate, 'migrate_to_weaviate'), \
            "Migration script missing main function"
        
        print("✅ Migration script is properly structured")
        
    except ImportError as e:
        pytest.fail(f"Failed to import migration script: {e}")
    except Exception as e:
        pytest.fail(f"Migration script validation failed: {e}")

def test_environment_variables():
    """Test that all required environment variables are set for migration"""
    required_vars = ["WEAVIATE_URL", "WEAVIATE_API_KEY"]
    optional_vars = ["WEAVIATE_CLASS_NAME"]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        pytest.skip(f"Missing required environment variables: {missing_vars}")
    
    # Check optional variables have defaults
    class_name = os.getenv("WEAVIATE_CLASS_NAME", "Product")
    assert class_name == "Product", f"Unexpected default class name: {class_name}"
    
    print("✅ All required environment variables are set")
    print(f"   WEAVIATE_URL: {os.getenv('WEAVIATE_URL')[:20]}...")
    print(f"   WEAVIATE_CLASS_NAME: {class_name}")

if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
