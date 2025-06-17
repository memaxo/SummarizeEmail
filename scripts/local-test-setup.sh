#!/bin/bash

# Local Testing Setup Script
# This script sets up a local testing environment with mock data and services

set -e

echo "=== Email Summarizer Local Testing Setup ==="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file"
else
    echo "✅ .env file already exists"
fi

# Check for required tools
echo ""
echo "Checking required tools..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi
echo "✅ Docker is installed"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9+ first."
    exit 1
fi
echo "✅ Python is installed"

# Start local services
echo ""
echo "Starting local services with Docker Compose..."
docker-compose up -d redis db
echo "✅ Redis and PostgreSQL are running"

# Wait for services to be ready
echo ""
echo "Waiting for services to be ready..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "redis.*Up"; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis failed to start"
    exit 1
fi

if docker-compose ps | grep -q "db.*Up"; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL failed to start"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo ""
echo "Installing Python dependencies..."
# Ensure we use the workspace-configured package installer
uv pip install -r requirements.txt
echo "✅ Dependencies installed"

# Initialize the database
echo ""
echo "Initializing database..."
python -c "
from app.db.session import init_db
init_db()
print('✅ Database initialized')
"

echo ""
echo "=== Local Testing Environment Ready ==="
echo ""
echo "Next steps:"
echo "1. Update .env file with your OpenAI API key"
echo "2. Run: source .venv/bin/activate"
echo "3. Run: python scripts/test-local-api.py"
echo "4. Or start the API: uvicorn app.main:app --reload"
echo ""
echo "Services running:"
echo "- Redis: localhost:6379"
echo "- PostgreSQL: localhost:5432"
echo "- API (when started): localhost:8000"
echo "- API Docs: localhost:8000/docs" 