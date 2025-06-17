#!/bin/bash

# Script to set up Google Cloud service account credentials for Gemini

set -e

echo "=== Google Cloud Service Account Setup for Gemini ==="
echo ""

# Check if .creds directory exists
if [ ! -d ".creds" ]; then
    echo "Creating .creds directory..."
    mkdir -p .creds
    echo "✅ Created .creds directory"
fi

# Check for the specific credential file
CRED_FILE=".creds/fox-et-video-intel-sandbox-24a1c0ca43a5.json"
if [ -f "$CRED_FILE" ]; then
    echo "✅ Found service account credentials: $CRED_FILE"
else
    echo "❌ Service account credentials not found at: $CRED_FILE"
    echo ""
    echo "Please place your service account JSON file at: $CRED_FILE"
    echo "Or update the GOOGLE_APPLICATION_CREDENTIALS path in your .env file"
    exit 1
fi

# Extract project ID from the credentials file
PROJECT_ID=$(grep -o '"project_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$CRED_FILE" | sed 's/.*: *"\([^"]*\)".*/\1/')

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Could not extract project ID from credentials file"
    exit 1
fi

echo "✅ Detected Google Cloud Project: $PROJECT_ID"

# Update or create .env file
echo ""
echo "Updating .env file with Gemini Vertex AI configuration..."

# Backup existing .env if it exists
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backed up existing .env file"
fi

# Check if .env exists and has Gemini config
if [ -f .env ]; then
    # Update existing .env
    if grep -q "GOOGLE_APPLICATION_CREDENTIALS" .env; then
        # Update existing values
        sed -i.tmp "s|GOOGLE_APPLICATION_CREDENTIALS=.*|GOOGLE_APPLICATION_CREDENTIALS=$CRED_FILE|" .env
        sed -i.tmp "s|GOOGLE_CLOUD_PROJECT=.*|GOOGLE_CLOUD_PROJECT=$PROJECT_ID|" .env
        rm -f .env.tmp
        echo "✅ Updated existing Gemini configuration in .env"
    else
        # Append new values
        cat >> .env << EOF

# Google Cloud Service Account Configuration
GOOGLE_APPLICATION_CREDENTIALS=$CRED_FILE
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL_NAME=gemini-2.5-flash
EOF
        echo "✅ Added Gemini configuration to .env"
    fi
else
    # Create new .env from example
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        touch .env
    fi
    
    cat >> .env << EOF
# LLM Provider Configuration
LLM_PROVIDER=gemini

# Google Cloud Service Account Configuration
GOOGLE_APPLICATION_CREDENTIALS=$CRED_FILE
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL_NAME=gemini-2.5-flash

# Local testing mode
USE_MOCK_GRAPH_API=true
MOCK_GRAPH_API_URL=http://localhost:8001

# Database (uses Docker container)
DATABASE_URL=postgresql://emailsummarizer:password123@localhost:5432/emailsummarizer

# Redis (uses Docker container)
REDIS_URL=redis://localhost:6379

# API Settings
API_TITLE=Email Summarizer API
API_VERSION=1.0.0
ENVIRONMENT=development
EOF
    echo "✅ Created new .env file with Gemini configuration"
fi

echo ""
echo "=== Configuration Complete ==="
echo ""
echo "Your app is now configured to use Gemini via Vertex AI with:"
echo "- Project: $PROJECT_ID"
echo "- Credentials: $CRED_FILE"
echo "- Model: gemini-2.5-flash"
echo ""
echo "To test the configuration, run:"
echo "  python scripts/test-gemini-connection.py"
echo ""
echo "To start the application:"
echo "  ./scripts/local-test-setup.sh" 