#!/bin/bash

# Comprehensive Local Testing Runner
# This script runs all local tests with mock data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Email Summarizer Comprehensive Local Testing ===${NC}"
echo ""

# Function to check if a process is running on a port
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    echo -n "Waiting for $name to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done
    echo -e " ${RED}✗${NC}"
    return 1
}

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup...${NC}"
    ./scripts/local-test-setup.sh
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Update .env file with test configuration
echo ""
echo -e "${BLUE}Configuring test environment...${NC}"
if [ -f .env ]; then
    # Backup existing .env
    cp .env .env.backup
    
    # Add test configuration
    cat >> .env << EOF

# Test Configuration
USE_MOCK_GRAPH_API=true
MOCK_GRAPH_API_URL=http://localhost:8001
EOF
    echo -e "${GREEN}✓${NC} Test configuration added to .env"
fi

# Start services
echo ""
echo -e "${BLUE}Starting services...${NC}"

# Start Docker services if not running
if ! docker-compose ps | grep -q "redis.*Up"; then
    echo "Starting Redis and PostgreSQL..."
    docker-compose up -d redis db
    sleep 5
fi

# Start mock Graph API
if ! check_port 8001; then
    echo "Starting Mock Graph API server..."
    python scripts/mock-graph-api.py &
    MOCK_API_PID=$!
    wait_for_service "http://localhost:8001/health" "Mock Graph API"
else
    echo -e "${GREEN}✓${NC} Mock Graph API already running"
fi

# Start the main API
if ! check_port 8000; then
    echo "Starting Email Summarizer API..."
    uvicorn app.main:app --reload --port 8000 &
    API_PID=$!
    wait_for_service "http://localhost:8000/health" "Email Summarizer API"
else
    echo -e "${GREEN}✓${NC} Email Summarizer API already running"
fi

# Run tests
echo ""
echo -e "${BLUE}Running tests...${NC}"
echo ""

# Run unit tests
echo -e "${YELLOW}1. Running unit tests...${NC}"
python -m pytest tests/ -v --tb=short || true

echo ""
echo -e "${YELLOW}2. Running API integration tests...${NC}"
python scripts/test-local-api.py

echo ""
echo -e "${YELLOW}3. Running load tests...${NC}"
if [ -f tests/load/test_load.py ]; then
    python tests/load/test_load.py || true
else
    echo "Load tests not found, skipping..."
fi

# Interactive testing menu
echo ""
echo -e "${BLUE}=== Interactive Testing Menu ===${NC}"
echo "Services are running. You can now:"
echo ""
echo "1. Open API docs: http://localhost:8000/docs"
echo "2. Open Mock Graph API: http://localhost:8001/docs"
echo "3. Run specific tests with pytest"
echo "4. Test with curl commands"
echo ""
echo -e "${YELLOW}Example curl commands:${NC}"
echo ""
echo "# Get mock emails:"
echo 'curl -H "Authorization: Bearer test-token" http://localhost:8001/v1.0/me/messages | jq'
echo ""
echo "# Summarize an email:"
echo 'curl -X POST http://localhost:8000/messages/msg001/summary \\'
echo '  -H "Content-Type: application/json" \\'
echo '  -d "{\"content\": \"Test email content\"}" | jq'
echo ""
echo "# Query with RAG:"
echo 'curl "http://localhost:8000/rag/query?q=budget+review" | jq'
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    
    # Kill processes if we started them
    if [ ! -z "$MOCK_API_PID" ]; then
        kill $MOCK_API_PID 2>/dev/null || true
    fi
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
    fi
    
    # Restore .env if we backed it up
    if [ -f .env.backup ]; then
        mv .env.backup .env
    fi
    
    echo -e "${GREEN}✓${NC} Cleanup complete"
}

# Set up trap for cleanup
trap cleanup EXIT

# Keep script running for interactive testing
echo ""
echo -e "${GREEN}Press Ctrl+C to stop all services and exit${NC}"
echo ""

# Wait for user to exit
while true; do
    sleep 1
done 