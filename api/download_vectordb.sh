#!/bin/bash
set -e

# Download vector database from Cloud Storage if not already present
if [ ! -d "/vectordb" ] || [ ! -f "/vectordb/chroma.sqlite3" ]; then
    echo "Vector database not found, downloading from Cloud Storage..."
    
    # Create vectordb directory
    mkdir -p /vectordb
    
    # Configure gcloud to use the default service account (Cloud Run metadata server)
    echo "Configuring gcloud authentication..."
    gcloud auth activate-service-account --key-file=/dev/null || true
    
    # Download from Cloud Storage
    if [ -n "$VECTORDB_GS_PATH" ]; then
        echo "Downloading from: $VECTORDB_GS_PATH"
        gsutil -m cp -r "$VECTORDB_GS_PATH" /vectordb
    else
        echo "VECTORDB_GS_PATH not set, using default path"
        # Default path - you can customize this
        gsutil -m cp -r "gs://shoptalk-data/vectordb" /vectordb
    fi
    
    echo "Vector database downloaded successfully"
else
    echo "Vector database already exists, skipping download"
fi

# Start the API server
exec "$@"
