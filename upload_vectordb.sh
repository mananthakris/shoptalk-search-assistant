#!/bin/bash
set -e

# Script to upload vector database to Google Cloud Storage
# Usage: ./upload_vectordb.sh <bucket-name>

if [ $# -eq 0 ]; then
    echo "Usage: $0 <bucket-name>"
    echo "Example: $0 my-shoptalk-bucket"
    exit 1
fi

BUCKET_NAME=$1
LOCAL_VECTORDB_PATH="./vectordb"
GS_PATH="gs://$BUCKET_NAME/vectordb"

echo "Uploading vector database to Cloud Storage..."
echo "Local path: $LOCAL_VECTORDB_PATH"
echo "Cloud Storage path: $GS_PATH"

# Check if local vectordb exists
if [ ! -d "$LOCAL_VECTORDB_PATH" ]; then
    echo "Error: Local vector database not found at $LOCAL_VECTORDB_PATH"
    echo "Please run 'make seed' first to build the vector database"
    exit 1
fi

# Check if gsutil is available
if ! command -v gsutil &> /dev/null; then
    echo "Error: gsutil not found. Please install Google Cloud SDK"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Create bucket if it doesn't exist
echo "Creating bucket if it doesn't exist..."
gsutil mb -p $(gcloud config get-value project) -c STANDARD -l us-central1 "gs://$BUCKET_NAME" 2>/dev/null || echo "Bucket already exists or creation failed"

# Upload vector database
echo "Uploading vector database files..."
gsutil -m cp -r "$LOCAL_VECTORDB_PATH" "gs://$BUCKET_NAME/"

echo "✅ Vector database uploaded successfully!"
echo "📋 Add this to your GitHub Secrets:"
echo "   VECTORDB_GS_PATH=gs://$BUCKET_NAME/vectordb"
echo ""
echo "🔧 To update the vector database in the future:"
echo "   1. Run 'make seed' to rebuild locally"
echo "   2. Run '$0 $BUCKET_NAME' to upload"
echo "   3. Redeploy your Cloud Run service"
