# Vertex AI Authentication Setup

## Overview

Vertex AI uses Google Cloud credentials instead of API keys. Here are the authentication options:

## Option 1: Application Default Credentials (ADC) - Recommended

This is the easiest method for local development:

```bash
# Install Google Cloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate with your Google account
gcloud auth application-default login

# Set your default project
gcloud config set project YOUR_PROJECT_ID
```

## Option 2: Service Account Key File

For production or CI/CD environments:

1. **Create a Service Account:**
   - Go to Google Cloud Console > IAM & Admin > Service Accounts
   - Create a new service account with Vertex AI User role
   - Download the JSON key file

2. **Set Environment Variable:**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account-key.json"
   ```

## Option 3: Environment Variables

Add to your `.env` file:

```bash
# Required for Vertex AI
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Optional - if using service account key
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

## Testing Authentication

Run this command to test your authentication:

```bash
gcloud auth list
```

You should see your authenticated account listed.

## Required Permissions

Your account/service account needs these roles:
- `Vertex AI User` (roles/aiplatform.user)
- `Storage Object Viewer` (if using Cloud Storage files)

## Model Availability

Vertex AI supports these models:
- `gemini-2.0-flash`
- `gemini-2.0-flash-lite` 
- `gemini-1.5-flash`
- `gemini-1.5-pro`

## Code Changes Required

Replace:
```python
from google import genai
client = genai.Client(api_key=api_key)
```

With:
```python
import vertexai
from vertexai.generative_models import GenerativeModel
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel(model_name)
``` 