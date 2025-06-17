# Outlook Email Summarizer API

This project provides a production-ready, containerized FastAPI service that summarizes Outlook emails. It's designed to be plugged into a **Custom GPT** as a single, powerful "Summarize Email" action, allowing users to get TL;DRs of their emails directly within ChatGPT.

The architecture is built for speed and enterprise-readiness, using Microsoft Graph for secure email access, LangChain for flexible LLM integration, and Redis for performance caching.

## Features

- **FastAPI Backend**: A robust, async-ready API built with Python and FastAPI.
- **Microsoft Graph Integration**: Securely fetches email content using MSAL for app-only authentication with least-privilege (`Mail.Read`) permissions.
- **Flexible LLM Support**: Switch between **Google Gemini** (default), **OpenAI** (`gpt-4o-mini`, etc.) and self-hosted **Ollama** models via a simple environment variable.
- **Advanced Summarization**:
    - **Single Email**: Get a quick summary for any specific email.
    - **Structured Output**: Extract key points, action items, and sentiment (Gemini/OpenAI only).
    - **Bulk Digest**: Generate a single "digest" summary from a list of emails.
    - **Daily Digest**: Automatically get a summary of all emails from the last 24 hours.
- **Powerful Email Search & Retrieval**:
    - **Full-Text Search**: Use Graph's `$search` functionality for broad queries.
    - **Granular Filtering**: Filter emails by sender, subject, read status, and date range.
    - **Full Email Content**: Retrieve the complete body of any email.
    - **Attachment Handling**: List and download attachments, including their raw `contentBytes`.
- **Semantic Search with RAG (Retrieval-Augmented Generation)**:
    - **Ingestion**: Asynchronously fetch emails and store their vector embeddings in a PostgreSQL database with `pgvector`.
    - **Semantic Query**: Find the most relevant emails based on the *meaning* of your query, not just keywords.
- **Performance Caching**: Integrated Redis caching for summary operations to reduce latency and cost.
- **Containerized**: Ships with a `Dockerfile` and `docker-compose.yml` for one-command local setup (including a Postgres + pgvector DB) and easy deployment.
- **Custom GPT Ready**: Includes a pre-built `openapi.yaml` specification for seamless integration as a GPT Action.
- **Production Ready**: Features include rate limiting, a health check endpoint, structured logging, and robust error handling.

---

## Architecture

```
┌───────────────────┐      ┌───────────────────────────┐      ┌──────────────────────────┐
│    Custom GPT     │      │   Summarizer API Service  │      │   Microsoft Graph API    │
│ (ChatGPT Interface) │<────>│ (FastAPI on your server)  │<────>│ (Outlook / M365)         │
└───────────────────┘      └───────────────────────────┘      └──────────────────────────┘
       │                          │ ▲                                │
       │                          │ │                                │
       ▼                          │ │                                ▼
┌───────────────────┐             │ └─────────┐                ┌──────────────┐
│  openapi.yaml   │             │           │                │ User's Mailbox │
│ (Defines Action)  │             │           ▼                └──────────────┘
└───────────────────┘      ┌──────────┴─────────┐      ┌──────────────────────────┐
                         │   LLM Provider   │      │      Redis Cache       │
                         │(Gemini/OpenAI/Ollama)│<────>│ (For storing summaries)  │
                         └──────────────────┘      └──────────────────────────┘
```

1.  A user asks the Custom GPT to summarize an email.
2.  The GPT, using its configured Action (`openapi.yaml`), calls your public `/summarize` endpoint with an email `msg_id`.
3.  The FastAPI service receives the request.
4.  It first checks Redis for a cached summary. If found, it's returned immediately.
5.  If not cached, it acquires an auth token and uses the Microsoft Graph API to securely fetch the email content for the configured user.
6.  The email content is passed to a LangChain summarization chain.
7.  The chain uses the configured LLM (Gemini, OpenAI or Ollama) to generate a summary.
8.  The summary is stored in Redis for future requests and returned to the GPT.

---

## Setup and Deployment

Follow these steps to get the service running.

### Step 1: Prerequisites - Azure AD App Registration

You need an Azure AD Application with permissions to read a specific user's mailbox.

1.  **Register an Application**:
    *   Go to the [Azure Portal](https://portal.azure.com/) > **Microsoft Entra ID** > **App registrations** > **New registration**.
    *   Give it a name (e.g., `EmailSummarizerAction`).
    *   Select **"Accounts in this organizational directory only"**.
    *   Click **Register**.

2.  **Get Credentials**:
    *   On the app's overview page, copy the **Application (client) ID** and **Directory (tenant) ID**. These are your `CLIENT_ID` and `TENANT_ID`.

3.  **Create a Client Secret**:
    *   Go to **Certificates & secrets** > **New client secret**.
    *   Add a description and select an expiry period.
    *   **IMPORTANT**: Copy the secret's **Value** immediately. This is your `CLIENT_SECRET`. You won't be able to see it again.

4.  **Add API Permissions**:
    *   Go to **API permissions** > **Add a permission** > **Microsoft Graph**.
    *   Select **Application permissions**.
    *   Search for `Mail.Read` and select it. **Do NOT select the delegated permission.**
    *   Click **Add permissions**.

5.  **Grant Admin Consent**:
    *   On the API permissions page, click the **"Grant admin consent for [Your Tenant]"** button. The status should change to "Granted".

6.  **Find the Target User ID**:
    *   Go to **Microsoft Entra ID** > **Users**.
    *   Find the user whose mailbox you want to access and click on their name.
    *   Copy the **Object ID**. This is your `TARGET_USER_ID`.

### Step 2: Configure Environment Variables

Create a `.env` file in the project root. You can copy the template:

```bash
cp .env.example .env
```

Now, open the `.env` file and fill in the values you gathered in Step 1, along with your LLM provider credentials and database settings.

```ini
# .env
TENANT_ID="COPIED_FROM_AZURE"
CLIENT_ID="COPIED_FROM_AZURE"
CLIENT_SECRET="COPIED_FROM_AZURE"
TARGET_USER_ID="COPIED_FROM_AZURE"

# LLM Provider Configuration
LLM_PROVIDER="gemini" # Options: "gemini" (default), "openai", or "ollama"

# For Google Gemini (default)
GOOGLE_API_KEY="your-google-api-key"
GEMINI_MODEL_NAME="gemini-2.5-flash"

# For OpenAI (alternative)
# OPENAI_API_KEY="sk-YOUR_OPENAI_KEY"
# OPENAI_MODEL_NAME="gpt-4o-mini"

# For Ollama (self-hosted)
# OLLAMA_BASE_URL="http://localhost:11434"
# OLLAMA_MODEL="llama2"

#
# PostgreSQL Database Settings
# These credentials are used by the FastAPI service to connect to the PostgreSQL
# database for the RAG functionality. They must match the credentials defined
# in docker-compose.yml for the 'db' service.
#
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_DB=email_rag_db
POSTGRES_SERVER=db
POSTGRES_PORT=5432
```

### Step 3: Run Locally with Docker Compose

With Docker installed, starting the service, Redis cache, and PostgreSQL database is a single command:

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.
- **API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
- **Metrics**: `http://localhost:8000/metrics`

### Step 4: Deploy to a Single EC2 Host

To get the prototype running on a public server, you can deploy it to an EC2 instance.

1.  **Launch an EC2 Instance**:
    *   **AMI**: Use Amazon Linux 2023 (as indicated by the `ec2-user`).
    *   **Instance Type**: `t3.small` is sufficient for the prototype.
    *   **Security Group (Firewall)**: Create a new security group and add **inbound rules** to allow traffic on:
        *   **Port 22 (SSH)** from your IP address for management.
        *   **Port 8000 (HTTP)** from `0.0.0.0/0` (or your IP) to access the FastAPI app.

2.  **SSH into the Instance and Install Dependencies**:
    ```bash
    # SSH into your new instance using your key
    ssh -i /path/to/your/jack-mazac-workbox.pem ec2-user@ec2-52-43-205-252.us-west-2.compute.amazonaws.com

    # Verify Python and Pip are installed (should be pre-installed on Amazon Linux 2023)
    python3 --version
    pip3 --version

    # Install Git and Docker
    sudo yum update -y
    sudo yum install git docker -y
    sudo service docker start
    sudo usermod -aG docker ec2-user # Log out and back in to apply group changes

    # Install uv (the fast Python package installer)
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add uv to the path for the current session
    source $HOME/.cargo/env
    ```

3.  **Clone and Run the Application**:
    ```bash
    # Clone your repository
    git clone https://github.com/<your-username>/SummarizeEmail.git
    cd SummarizeEmail

    # Create and populate the .env file with your credentials
    cp .env.example .env
    nano .env # Or your preferred editor

    # Run the application in detached mode
    docker compose up -d --build
    ```

4.  **Access Your Service**:
    *   Your API is now available at `http://ec2-52-43-205-252.us-west-2.compute.amazonaws.com:8000`.
    *   Test the health check: `curl http://ec2-52-43-205-252.us-west-2.compute.amazonaws.com:8000/health`

### Step 5: Set Up the Custom GPT Action

1.  **Update the OpenAPI Spec**:
    *   Open `openapi.yaml`.
    *   Change the `url` under `servers` to your public EC2 endpoint.
    ```yaml
    servers:
      - url: http://ec2-52-43-205-252.us-west-2.compute.amazonaws.com:8000
    ```

2.  **Create the Custom GPT**:
    *   Go to ChatGPT > **Explore GPTs** > **Create a GPT**.
    *   In the **Configure** tab, click **"Create new action"**.
    *   Select **"Import from URL"** and provide the raw link to your hosted `openapi.yaml`, or paste the content directly.
    *   The action `summarizeEmail` should appear.
    *   No authentication is needed for the action itself, as the API is open (but can be secured further if needed).

3.  **Configure the GPT**:
    *   Give your GPT a name and description.
    *   Provide clear instructions. Example:
    > You are an expert assistant who can summarize my Outlook emails. When I ask you to summarize an email, you will ask for the message ID. Then you will use the 'summarizeEmail' action to fetch the summary. Present the summary clearly to me.

4.  **Test It**:
    *   Find a message ID from an email in the target user's Outlook. (You can get this from the Graph Explorer or by using other Graph API calls).
    *   Start a chat with your new GPT and say: "Summarize the email with ID AAMkAGI1ZTMx..."
    *   The GPT should call your API and return the summary.

---

## API Endpoints

The API is now organized into logical sections for clarity.

### Email Search & Retrieval

#### `GET /emails`
Search and filter through the target user's mailbox.

- **Query Parameters**:
    - `search` (string, optional): A free-text search query (uses Graph's `$search`).
    - `from_address` (string, optional): Filter by sender's email address.
    - `subject_contains` (string, optional): Filter by a keyword in the subject.
    - `is_unread` (bool, optional): Filter for only unread emails.
    - `start_date` (datetime, optional): The start of a date range filter.
    - `end_date` (datetime, optional): The end of a date range filter.
    - `limit` (int, optional, default: 25): The maximum number of emails to return.
- **Success Response (200)**: A JSON array of `Email` objects.

#### `GET /messages/{message_id}`
Retrieves the full content of a single email message.

- **Path Parameter**: `message_id` (string, required).
- **Success Response (200)**: A single `Email` object.

#### `GET /messages/{message_id}/attachments`
Lists all attachments for a given email.

- **Path Parameter**: `message_id` (string, required).
- **Success Response (200)**: A JSON array of `Attachment` metadata objects.

#### `GET /messages/{message_id}/attachments/{attachment_id}`
Retrieves a single attachment, including its base64-encoded content.

- **Path Parameters**: `message_id`, `attachment_id` (strings, required).
- **Success Response (200)**: A single `Attachment` object with the `contentBytes` field populated.

### Summarization

#### `GET /messages/{message_id}/summary`
Generates a summary for a single email.

-   **Path Parameter**: `message_id` (string, required).
-   **Success Response (200)**: A JSON object with the summary.

#### `POST /summaries`
Generates a single "digest" summary from a list of email IDs.

- **Request Body**: A JSON object with a `message_ids` key pointing to a list of strings.
  ```json
  {
    "message_ids": ["id1", "id2", "id3"]
  }
  ```
- **Success Response (200)**: A JSON object containing the combined `digest`.

#### `GET /summaries/daily`
Generates a digest summary of all emails received in the last 24 hours.

- **Success Response (200)**: A JSON object containing the `digest`.

### Semantic Search (RAG)

#### `POST /rag/ingest`
Triggers a background task to fetch and embed emails into the vector database.

- **Query Parameter**: `query` (string, optional): A Graph API query string (like the one for `/emails`) to filter which emails to ingest. If omitted, it may ingest recent emails by default.
- **Success Response (202 - Accepted)**: A confirmation message that the ingestion has started.

#### `GET /rag/query`
Performs a semantic search against the ingested emails.

- **Query Parameter**: `q` (string, required): The natural language query to search for.
- **Success Response (200)**: A list of relevant `Email` objects found in the vector database.

### Monitoring

#### `GET /health`

A health check endpoint to monitor the service status and its dependency on Redis.

-   **Success Response (200)**: A JSON object indicating the status of the API and its connection to Redis.

#### `GET /metrics`

An endpoint that exposes Prometheus-compatible metrics for monitoring application performance, request latency, and status codes.

---

## Testing

### Unit and Integration Tests

The project includes a comprehensive test suite using `pytest`. To run the tests, ensure you have installed the development dependencies:

```bash
uv pip install -r requirements-dev.txt
pytest
```

### Load Testing

This project uses [Locust](https://locust.io/) to simulate user traffic and measure performance under load. A `locust` service is defined in the `docker-compose.yml` file for easy setup.

1.  **Start the Services**:
    From the project root, run:
    ```bash
    docker-compose up --build
    ```
    This will start the `summarizer-api`, `redis`, and `locust` services.

2.  **Open the Locust Web UI**:
    Navigate to `http://localhost:8089` in your web browser.

3.  **Start a New Load Test**:
    *   **Number of users**: Enter the total number of concurrent users to simulate (e.g., `100`).
    *   **Spawn rate**: Enter the number of users to start per second (e.g., `10`).
    *   **Host**: The host should already be set to `http://summarizer-api:8000`.
    *   Click **Start swarming**.

4.  **View Results**:
    The "Charts" and "Statistics" tabs in the Locust UI will show real-time data on request rates, response times, and any failures. 