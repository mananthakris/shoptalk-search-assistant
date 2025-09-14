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
    
    # Configure gcloud to use application default credentials
    gcloud config set auth/use_application_default_credentials true
    gcloud config set account "$SERVICE_ACCOUNT_EMAIL"
    
    # Verify authentication is working
    echo "Testing authentication..."
    gcloud auth list
    
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
