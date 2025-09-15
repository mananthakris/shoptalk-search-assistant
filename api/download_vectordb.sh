#!/bin/bash
set -e

# Download vector database from Cloud Storage if not already present
if [ ! -d "/vectordb" ] || [ ! -f "/vectordb/chroma.sqlite3" ]; then
    echo "Vector database not found, downloading from Cloud Storage..."
    
    # Create vectordb directory
    mkdir -p /vectordb
    
    # Set up authentication for gsutil to use the Cloud Run service account
    echo "Setting up authentication for gsutil..."
    
    # Get the service account email from metadata server
    SERVICE_ACCOUNT_EMAIL=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email" -H "Metadata-Flavor: Google")
    echo "Using service account: $SERVICE_ACCOUNT_EMAIL"
    
    # Set environment variables for Google Cloud libraries
    export GOOGLE_CLOUD_PROJECT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")
    echo "Using project: $GOOGLE_CLOUD_PROJECT"
    
    # Don't configure gcloud - let it use the metadata server automatically
    echo "Using Cloud Run metadata server for authentication..."
    
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
