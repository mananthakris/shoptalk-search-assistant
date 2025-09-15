#!/bin/bash
set -e

# Download vector database from Cloud Storage if not already present
if [ ! -d "/vectordb" ] || [ ! -f "/vectordb/chroma.sqlite3" ]; then
    echo "Vector database not found, downloading from Cloud Storage..."
    
    # Create vectordb directory
    mkdir -p /vectordb
    
    # Get access token from metadata server
    echo "Getting access token from metadata server..."
    TOKEN_RESPONSE=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
        -H "Metadata-Flavor: Google")
    
    # Extract access token using grep and sed (no jq dependency)
    ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\([^"]*\)"/\1/')
    
    if [ -z "$ACCESS_TOKEN" ]; then
        echo "ERROR: Failed to get access token from metadata server"
        echo "Response: $TOKEN_RESPONSE"
        exit 1
    fi
    
    echo "Access token obtained successfully"
    
    # Download from Cloud Storage using REST API
    if [ -n "$VECTORDB_GS_PATH" ]; then
        echo "Downloading from: $VECTORDB_GS_PATH"
        # Extract bucket and object path from gs:// path
        BUCKET_PATH=${VECTORDB_GS_PATH#gs://}
        BUCKET_NAME=${BUCKET_PATH%%/*}
        OBJECT_PATH=${BUCKET_PATH#*/}
        
        # Download using curl with access token
        curl -H "Authorization: Bearer $ACCESS_TOKEN" \
             -o "/vectordb/chroma.sqlite3" \
             "https://storage.googleapis.com/storage/v1/b/$BUCKET_NAME/o/$OBJECT_PATH%2Fchroma.sqlite3?alt=media"
    else
        echo "VECTORDB_GS_PATH not set, using default path"
        # Default path
        curl -H "Authorization: Bearer $ACCESS_TOKEN" \
             -o "/vectordb/chroma.sqlite3" \
             "https://storage.googleapis.com/storage/v1/b/shoptalk-data/o/vectordb%2Fchroma.sqlite3?alt=media"
    fi
    
    echo "Vector database downloaded successfully"
else
    echo "Vector database already exists, skipping download"
fi

# Start the API server
exec "$@"
