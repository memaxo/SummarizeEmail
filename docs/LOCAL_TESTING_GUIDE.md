# Local Testing Guide

This guide helps you test the Email Summarizer API locally without Azure credentials.

## Quick Start

1. **Set up your environment:**
   ```bash
   # Choose your LLM provider (Gemini is default)
   # For Google Gemini (recommended):
   export GOOGLE_API_KEY="your-google-api-key-here"
   
   # OR for OpenAI:
   export OPENAI_API_KEY="your-openai-api-key-here"
   
   # Run the setup script
   ./scripts/local-test-setup.sh
   ```

2. **Start all services:**
   ```bash
   ./scripts/run-local-tests.sh
   ```

   This will:
   - Start Redis and PostgreSQL via Docker
   - Start the Mock Microsoft Graph API (port 8001)
   - Start the Email Summarizer API (port 8000)
   - Run automated tests
   - Keep services running for manual testing

## LLM Provider Configuration

The app supports multiple LLM providers:

### Google Gemini (Default)
```bash
# In .env file:
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-google-api-key-here
GEMINI_MODEL_NAME=gemini-2.5-flash  # Uses the latest Gemini 2.5 Flash model
```

### OpenAI
```bash
# In .env file:
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL_NAME=gpt-4o-mini
```

## Testing Options

### 1. Interactive API Documentation

- **Main API**: http://localhost:8000/docs
- **Mock Graph API**: http://localhost:8001/docs

### 2. Command Line Testing

```bash
# Get mock emails
curl -H "Authorization: Bearer test-token" \
  http://localhost:8001/v1.0/me/messages | jq

# Search emails via our API
curl "http://localhost:8000/emails/search?query=budget" | jq

# Summarize an email (basic)
curl -X POST http://localhost:8000/messages/msg001/summary | jq

# Summarize with structured output (Gemini/OpenAI only)
curl -X POST "http://localhost:8000/messages/msg001/summary?structured=true" | jq

# Bulk summarization
curl -X POST http://localhost:8000/summaries/bulk \
  -H "Content-Type: application/json" \
  -d '{"message_ids": ["msg001", "msg002", "msg003"]}' | jq

# RAG query
curl "http://localhost:8000/rag/query?q=what+are+the+budget+issues" | jq
```

### 3. Python Testing Script

```bash
# Run the comprehensive test suite
python scripts/test-local-api.py
```

### 4. Jupyter Notebook Testing

```bash
# Start Jupyter and open the interactive notebook
jupyter notebook scripts/interactive-testing.ipynb
```

### 5. Unit Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run specific test files
pytest tests/test_emails_endpoints.py -v
pytest tests/test_summaries_endpoints.py -v
pytest tests/test_rag_endpoints.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Mock Data

The Mock Graph API generates realistic email data including:
- Various email subjects (budget, security, team updates, etc.)
- Different senders
- Realistic timestamps
- Email bodies with actionable content

## Testing Scenarios

### Basic Functionality
1. **Email Search**: Test searching with different queries
2. **Single Summarization**: Summarize individual emails
3. **Structured Summarization**: Get key points and action items (Gemini/OpenAI only)
4. **Bulk Summarization**: Summarize multiple emails at once
5. **RAG Queries**: Ask questions about your email content

### Performance Testing
1. **Caching**: Verify Redis caching improves response times
2. **Concurrent Requests**: Test API under load
3. **Response Times**: Measure summarization speed

### Error Handling
1. **Invalid Email IDs**: Test with non-existent email IDs
2. **API Limits**: Test rate limiting behavior
3. **Network Errors**: Test resilience to service failures

## Environment Variables

For local testing, these are automatically set:
```bash
USE_MOCK_GRAPH_API=true
MOCK_GRAPH_API_URL=http://localhost:8001
```

## Troubleshooting

### Services won't start
```bash
# Check if ports are already in use
lsof -i :8000  # Main API
lsof -i :8001  # Mock API
lsof -i :6379  # Redis
lsof -i :5432  # PostgreSQL

# Stop all services and restart
docker-compose down
pkill -f "uvicorn"
```

### Database issues
```bash
# Reset the database
docker-compose down -v
docker-compose up -d redis db
python -c "from app.db.session import init_db; init_db()"
```

### Mock API not responding
```bash
# Restart the mock API
pkill -f "mock-graph-api"
python scripts/mock-graph-api.py &
```

## Advanced Testing

### Custom Mock Data
Edit `scripts/mock-graph-api.py` to add custom email scenarios.

### Load Testing
```bash
# Install locust
pip install locust

# Run load tests
locust -f tests/load/test_load.py --host=http://localhost:8000
```

### Integration with Real Graph API
To test with real Microsoft Graph API (requires Azure setup):
1. Set `USE_MOCK_GRAPH_API=false` in `.env`
2. Add your Azure credentials
3. Restart the API

## Next Steps

Once local testing is complete:
1. Set up Azure App Registration
2. Configure production environment variables
3. Deploy to EC2
4. Set up monitoring and logging 