# Outlook Email Summarizer API

This project provides a production-ready, containerized FastAPI service that summarizes Outlook emails. It's designed to be plugged into a **Custom GPT** as a single, powerful "Summarize Email" action, allowing users to get TL;DRs of their emails directly within ChatGPT.

The architecture is built for speed and enterprise-readiness, using Microsoft Graph for secure email access, LangChain for flexible LLM integration, and Redis for performance caching.

## Features

- **FastAPI Backend**: A robust, async-ready API built with Python and FastAPI.
- **Microsoft Graph Integration**: Securely fetches email content using MSAL for app-only authentication with least-privilege (`Mail.Read`) permissions.
- **Flexible LLM Support**: Switch between **OpenAI** (`gpt-4o-mini`, etc.) and self-hosted **Ollama** models (e.g., `llama3`) via a simple environment variable.
- **LangChain Powered**: Utilizes LangChain's `map-reduce` summarization chain, which can handle emails of any length by intelligently splitting and summarizing content.
- **Performance Caching**: Integrated Redis caching to provide instant responses for previously summarized emails, reducing latency and cost.
- **Containerized**: Ships with a `Dockerfile` and `docker-compose.yml` for one-command local setup and easy deployment.
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
                         │ (OpenAI or Ollama) │<────>│ (For storing summaries)  │
                         └──────────────────┘      └──────────────────────────┘
```

1.  A user asks the Custom GPT to summarize an email.
2.  The GPT, using its configured Action (`openapi.yaml`), calls your public `/summarize` endpoint with an email `msg_id`.
3.  The FastAPI service receives the request.
4.  It first checks Redis for a cached summary. If found, it's returned immediately.
5.  If not cached, it acquires an auth token and uses the Microsoft Graph API to securely fetch the email content for the configured user.
6.  The email content is passed to a LangChain summarization chain.
7.  The chain uses the configured LLM (OpenAI or Ollama) to generate a summary.
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

Now, open the `.env` file and fill in the values you gathered in Step 1, along with your OpenAI API key if you're using it.

```ini
# .env
TENANT_ID="COPIED_FROM_AZURE"
CLIENT_ID="COPIED_FROM_AZURE"
CLIENT_SECRET="COPIED_FROM_AZURE"
TARGET_USER_ID="COPIED_FROM_AZURE"

LLM_PROVIDER="openai" # or "ollama"
OPENAI_API_KEY="sk-YOUR_OPENAI_KEY"
# ... other settings
```

### Step 3: Run Locally with Docker Compose

With Docker installed, starting the service is a single command:

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

### `GET /summarize`

Summarizes an email.

-   **Query Parameter**: `msg_id` (string, required) - The Microsoft Graph ID of the email.
-   **Success Response (200)**: A JSON object with the summary, message ID, and cache status.
-   **Error Responses**: Handles 404 (Not Found), 429 (Rate Limit Exceeded), and 5xx errors gracefully.

### `GET /health`

A health check endpoint to monitor the service status and its dependency on Redis.

-   **Success Response (200)**: A JSON object indicating the status of the API and its connection to Redis.

### `GET /metrics`

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