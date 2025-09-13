# Cloud Storage Setup Instructions

This guide will help you set up Google Cloud Storage for your ShopTalk Search Assistant deployment.

## 🎯 Overview

Your application will:
- **Local Development**: Continue using the local `vectordb` folder mount
- **Production**: Download vector database from Cloud Storage on container startup

## 📋 Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Google Cloud SDK** installed locally
3. **Vector database** built locally (`make seed`)

## 🚀 Step-by-Step Setup

### 1. Create Cloud Storage Bucket

#### Option A: Using Google Cloud Console (Web UI)

1. **Go to Cloud Storage**:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to **Cloud Storage** → **Buckets**

2. **Create New Bucket**:
   - Click **"CREATE BUCKET"**
   - **Name**: `your-project-shoptalk-vectordb` (must be globally unique)
   - **Location**: `us-central1` (or your preferred region)
   - **Storage class**: `Standard`
   - **Access control**: `Uniform`
   - Click **"CREATE"**

#### Option B: Using Command Line

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Create bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://your-project-shoptalk-vectordb
```

### 2. Upload Vector Database

#### Build Local Vector Database
```bash
# Make sure you have the vector database built locally
make seed
```

#### Upload to Cloud Storage
```bash
# Use the provided script
./upload_vectordb.sh your-project-shoptalk-vectordb

# Or manually with gsutil
gsutil -m cp -r ./vectordb gs://your-project-shoptalk-vectordb/
```

### 3. Configure GitHub Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

Add these secrets:

#### Required Secrets
```bash
# GCP Configuration
GCP_CREDENTIALS          # Service account JSON (see step 4) - email extracted automatically
GCP_PROJECT_ID          # Your GCP project ID
GCP_REGION             # us-central1 (or your region)
# SERVICE_ACCOUNT_EMAIL  # No longer needed - extracted from GCP_CREDENTIALS

# Application Configuration  
OPENAI_API_KEY         # Your OpenAI API key
OPENAI_BASE_URL        # https://api.openai.com/v1 (optional)
PARSE_MODEL           # gpt-4o-mini
NLG_MODEL             # gpt-4o-mini

# NEW: Vector Database Configuration
VECTORDB_GS_PATH      # gs://your-project-shoptalk-vectordb/vectordb
```

### 4. Create Service Account

#### Using Google Cloud Console

1. **Go to IAM & Admin**:
   - Navigate to **IAM & Admin** → **Service Accounts**

2. **Create Service Account**:
   - Click **"CREATE SERVICE ACCOUNT"**
   - **Name**: `shoptalk-deploy`
   - **Description**: `Service account for ShopTalk deployment`
   - Click **"CREATE AND CONTINUE"**

3. **Grant Roles**:
   - **Cloud Run Admin**: Deploy and manage Cloud Run services
   - **Storage Admin**: Access Cloud Storage bucket
   - **Service Account User**: Use service accounts
   - Click **"CONTINUE"** → **"DONE"**

4. **Grant Bucket Access** (Important for private buckets):
   - Go to **Cloud Storage** → **Buckets**
   - Click on your bucket name
   - Go to **"PERMISSIONS"** tab
   - Click **"GRANT ACCESS"**
   - **New principals**: `shoptalk-deploy@your-project.iam.gserviceaccount.com`
   - **Role**: `Storage Object Viewer`
   - Click **"SAVE"**

5. **Create Key**:
   - Click on the service account
   - Go to **"KEYS"** tab
   - Click **"ADD KEY"** → **"Create new key"**
   - Choose **JSON** format
   - Download the JSON file

6. **Add to GitHub Secrets**:
   - Copy the entire JSON content
   - Add as `GCP_CREDENTIALS` secret in GitHub
   - The service account email is automatically extracted from the JSON

#### Using Command Line

```bash
# Create service account
gcloud iam service-accounts create shoptalk-deploy \
    --description="Service account for ShopTalk deployment" \
    --display-name="ShopTalk Deploy"

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:shoptalk-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:shoptalk-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:shoptalk-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# Grant bucket access (replace YOUR_BUCKET_NAME with your actual bucket name)
gsutil iam ch serviceAccount:shoptalk-deploy@$PROJECT_ID.iam.gserviceaccount.com:objectViewer gs://YOUR_BUCKET_NAME

# Create and download key
gcloud iam service-accounts keys create shoptalk-deploy-key.json \
    --iam-account=shoptalk-deploy@$PROJECT_ID.iam.gserviceaccount.com

# Copy the JSON content to GitHub Secrets as GCP_CREDENTIALS
cat shoptalk-deploy-key.json

# Service account email is automatically extracted from GCP_CREDENTIALS
echo "Service account created: shoptalk-deploy@$PROJECT_ID.iam.gserviceaccount.com"
```

### 5. Enable Required APIs

```bash
# Enable required Google Cloud APIs
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 6. Deploy

#### Automatic Deployment
```bash
# Push to main branch to trigger deployment
git add .
git commit -m "Add Cloud Storage support"
git push origin main
```

#### Manual Deployment (if needed)
```bash
# Build and push images
docker build -t ghcr.io/your-org/shoptalk-api:latest -f api/Dockerfile ./api
docker build -t ghcr.io/your-org/shoptalk-ui:latest -f ui/Dockerfile ./ui

docker push ghcr.io/your-org/shoptalk-api:latest
docker push ghcr.io/your-org/shoptalk-ui:latest

# Deploy to Cloud Run
gcloud run deploy shoptalk-api \
  --image ghcr.io/your-org/shoptalk-api:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --port 8000 \
  --set-env-vars "OPENAI_API_KEY=your-key,DB_PATH=/vectordb,VECTORDB_GS_PATH=gs://your-bucket/vectordb"
```

## 🔍 Verification

### Check Deployment
```bash
# List Cloud Run services
gcloud run services list --region=us-central1

# Check service logs
gcloud run services logs read shoptalk-api --region=us-central1
```

### Troubleshooting Storage Access Issues

If you see errors like `401 Anonymous caller does not have storage.objects.get access`:

1. **Check service account permissions**:
   ```bash
   # Get the service account email
   gcloud run services describe shoptalk-api --region=us-central1 --format='value(spec.template.spec.serviceAccountName)'
   
   # Check bucket permissions
   gsutil iam get gs://your-bucket-name
   ```

2. **Grant Storage Object Viewer role**:
   ```bash
   # Replace with your actual service account email and bucket name
   gsutil iam ch serviceAccount:shoptalk-deploy@your-project.iam.gserviceaccount.com:objectViewer gs://your-bucket-name
   ```

3. **Verify the service account has the right roles**:
   ```bash
   gcloud projects get-iam-policy your-project-id --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:shoptalk-deploy@your-project.iam.gserviceaccount.com"
   ```

### Test the Application
1. **Get service URLs**:
   ```bash
   gcloud run services describe shoptalk-api --region=us-central1 --format='value(status.url)'
   gcloud run services describe shoptalk-ui --region=us-central1 --format='value(status.url)'
   ```

2. **Test API health**:
   ```bash
   curl https://your-api-url/health
   ```

3. **Test search**:
   ```bash
   curl "https://your-api-url/answer?q=red%20shoes&k=5"
   ```

## 🔄 Updating Vector Database

When you need to update the vector database:

```bash
# 1. Rebuild locally
make seed

# 2. Upload to Cloud Storage
./upload_vectordb.sh your-project-shoptalk-vectordb

# 3. Redeploy (or wait for next push to main)
git add . && git commit -m "Update vector database" && git push origin main
```

## 💰 Cost Estimation

For a typical setup:
- **Cloud Storage**: ~$0.02/GB/month (for 1GB vector DB = $0.02/month)
- **Cloud Run**: Pay per request (~$0.40/million requests)
- **Download costs**: ~$0.12/GB (one-time per container start)

**Total**: ~$5-15/month for moderate usage

## 🚨 Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   # Check service account permissions
   gcloud projects get-iam-policy $PROJECT_ID
   ```

2. **Bucket Not Found**:
   ```bash
   # List buckets
   gsutil ls
   ```

3. **Download Fails**:
   ```bash
   # Check bucket contents
   gsutil ls -r gs://your-bucket/vectordb
   ```

4. **Container Startup Slow**:
   - First startup downloads vector DB (30-60 seconds)
   - Subsequent starts are faster (cached)

### Debug Commands
```bash
# Check Cloud Run logs
gcloud run services logs read shoptalk-api --region=us-central1 --limit=50

# Check bucket permissions
gsutil iam get gs://your-bucket

# Test download manually
gsutil -m cp -r gs://your-bucket/vectordb /tmp/test-download
```

## ✅ Success Checklist

- [ ] Cloud Storage bucket created
- [ ] Vector database uploaded to bucket
- [ ] Service account created with proper roles
- [ ] GitHub secrets configured
- [ ] APIs enabled
- [ ] Deployment successful
- [ ] Health check passes
- [ ] Search functionality works

Your ShopTalk Search Assistant is now ready for production! 🎉
