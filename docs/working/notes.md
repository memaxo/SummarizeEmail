Here’s what we need to know about Azure permissions and the proposed prototype environment.

1. Do we need Azure admin access?  
  • Yes — but only once. To read users’ Outlook mail with an “app-only” approach, we must create an Azure AD application and grant it **Mail.Read (Application)** permission. Granting that permission requires a **tenant-wide admin consent**. After the consent is given, day-to-day development can proceed with the app’s client ID and secret; no further admin interaction is normally required.  
  • If we take a “delegated” flow (acting as each signed-in user), admin consent isn’t needed, but every user would have to sign in individually, which is awkward for an automated GPT action. So app-only + admin consent is the cleaner path.

2. Prototype environment – suggested setup  
  • Source Control & CI: GitHub → GitHub Actions CI workflow (`lint → tests → docker build`).  
  • Container Registry: GitHub Container Registry or Azure Container Registry (ACR).  
  • Staging Deploy: Azure Container Apps (or Azure Web App for Containers), pulling the built image on each push to `main`.  
  • Secrets: store `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, OpenAI key, and Redis URL in Azure Key Vault or GitHub Actions secrets; inject them as container environment variables.  
  • Data Services:  
    – Redis ( Azure Cache for Redis Basic tier) for caching.  
    – Optional Postgres with pgvector for future RAG work (skip in week 1).  
  • Observability: enable Container Apps’ built-in Log Analytics workspace for logs and metrics.

3. Local dev workflow  
  • `docker-compose up` spins up FastAPI + Redis.  
  • `.env` file contains a non-production OpenAI key and the Azure app credentials.  
  • Ngrok (or Azure Dev Tunnels) exposes the local API so Gabriella can import the OpenAPI spec into a test GPT.

4. Deployment flow (end of Week 1)  
  1. Code merged to `main` → GitHub Actions builds and pushes image to registry.  
  2. Action deploys to the staging Container App using the image tag.  
  3. Smoke test job calls `/health` and a sample `/summarize` to confirm everything works.  
  4. Share the staging URL + an ngrok tunnel as fall-back for GPT testing.

In short: we’ll request a one-time admin consent to the Mail.Read permission, store the resulting app credentials as secrets, and rely on our standard GitHub-to-Azure container pipeline for everything else.


---



Below is a gap-analysis of the current scaffold versus the expanded “real-world” use-cases you listed, followed by a concrete REST/RPC surface that would cover them.  Nothing has to be implemented immediately, but agreeing on the surface now avoids painful breaking changes later.

────────────────────────────────────────────────────────────────────────
1.  Gaps & Architectural Considerations
────────────────────────────────────────────────────────────────────────
A.  Scope of a “summary”  
   • Today we only support a single message-ID.  
   • Daily / weekly digests, project-based digests, or ad-hoc “all unread” queries require:
     –  a bulk email fetch layer (filtering, paging, batching).  
     –  aggregation logic (map→reduce across message set).  
     –  optional post-processing (ranking, grouping by thread, priority, etc.).

B.  Retrieval-Augmented Generation (RAG) over mailboxes  
   • We need long-term vector storage (pgvector, Redis-Vector, or Chroma) and an ingestion/refresh job that:
     –  embeds email bodies + attachment text.  
     –  stores metadata (message-id, thread-id, from, to, date, labels, …).  
   • RAG endpoints can then accept natural-language questions or a list of IDs and return grounded answers plus source cites.

C.  Attachments  
   • Graph gives attachment metadata and download URLs.  
   • We’ll need file-type detection + text extraction (pdfplumber, python-docx, textract) before embedding/summarising.  
   • Large files → async processing or streaming back progress.

D.  Searching / Regex  
   • Expose Graph’s `$search`, `$filter`, and/or full-text vector search through a thin endpoint.  
   • For local regex across many mails, fetching >10 MB of bodies synchronously will time-out; push that into the RAG store or background job.

E.  Async / Long-running jobs  
   • Digest over thousands of mails will exceed a single HTTP request.  
   • Pattern: submit job → get job-id → poll `/jobs/{id}` or receive webhook/SSE.

F.  Security / Permissions  
   • Fine-grained Graph scopes (Mail.ReadBasic vs Mail.Read) already planned.  
   • If you add “send email” (e.g., return digest via Outlook), need Mail.Send + admin review.  
   • Attachments can contain PII; log scrubbing & S3-style pre-signed URLs recommended.

────────────────────────────────────────────────────────────────────────
2.  Recommended Additional Endpoints
────────────────────────────────────────────────────────────────────────
Namespace: `/v1` (prefix omitted for brevity)

A.  Email Retrieval & Search
1.  `GET  /emails`  
    query params: `from`, `to`, `start_date`, `end_date`, `folder`, `is_unread`, `top`, `skip`, `search`, `regex`  
    ➜ returns minimal envelope list (id, subject, from, date, hasAttachments).

2.  `GET  /emails/{id}`  
    ➜ full body (plain-text) + attachment metadata.

3.  `GET  /emails/{id}/attachments/{att_id}`  
    ➜ streams raw bytes or text-extracted preview (`?text=true`).

B.  Summarisation
4.  `POST /summaries`  (bulk)  
    body:
    ```
    {
      "ids": ["id1", "id2", …],
      "mode": "digest" | "individual",
      "strategy": "map_reduce" | "refine",
      "return_sources": true
    }
    ```  
    ➜ returns `digest` string + per-message summaries + sources; caches each.

5.  `GET /summaries/daily`  
    query: `date=YYYY-MM-DD` (default=today)  
    ➜ server calculates message set (e.g., inbox for that day) and returns digest.  

6.  `GET /summaries/weekly`  
    query: `start=YYYY-MM-DD` (7-day window)  

C.  RAG / Knowledge-Base
7.  `POST /rag/query`  
    body: `{ "question": "...", "filter": { ... }, "top_k": 8 }`  
    ➜ returns answer, supporting passages, message-ids, score.

8.  `POST /rag/ingest`  (admin/protected)  
    body: `{ "range": {"start":"...", "end":"..."}, "force": false }`  
    ➜ kicks off (or re-runs) embedding job; returns job-id.

D.  Jobs & Monitoring
9.  `GET /jobs/{job_id}`  
    ➜ `{ status: queued|running|succeeded|failed, progress: 0-100, result_url }`

E.  Misc / Utilities
10. `GET /health`           (already in place)  
11. `GET /metrics`          (Prometheus scrape)  
12. `GET /rate-limits`      (current user’s remaining quota)

────────────────────────────────────────────────────────────────────────
3.  Implementation Road-map (incremental)
────────────────────────────────────────────────────────────────────────
1) **Refactor Email Service** – Wrap Graph calls behind a repository that supports:
   • single mail fetch   • batch fetch (graph `$batch` API)  
   • attachment fetch    • filter/search helpers.

2) **Batch Summariser** – Accept list of bodies, run map→reduce → optional digest; reuse existing LangChain chain.

3) **Vector Store** – Choose pgvector (fits Docker Compose), create `email_embeddings` table, write ingestion worker (FastAPI BackgroundTask, Celery, or RQ).

4) **Attachment Extraction** – Integrate `textract` plugin / tika-py; store extraction in Redis (short-term) and pgvector (long-term).

5) **Async Job Framework** – Light-weight: FastAPI + Redis queue + worker process; heavy-weight: Celery + Redis/-RQ.

6) **OpenAPI Spec v1.1** – Add new paths; mark long-running endpoints as `202 Accepted` with `Operation-Location` header (job polling URL).

7) **GPT Action Mapping** –  
   • Expose `/emails`, `/summaries`, `/rag/query` actions.  
   • Provide examples in system prompt: “When user asks for a weekly summary, call `GET /summaries/weekly?start=YYYY-MM-DD`”.

────────────────────────────────────────────────────────────────────────
4.  Quick Wins You Can Deliver Next Sprint
────────────────────────────────────────────────────────────────────────
• Add **`POST /summaries`** (bulk) – minimal code change: accept list → loop existing `summarize_email` service → combine.  
• Add **`GET /emails`** with Graph `$filter`/`$top` passthrough (lets GPT collect IDs for the bulk call).  
• Introduce **embedding worker** with LangChain’s `OpenAIEmbeddings` + pgvector; RAG query endpoint can come right after.  
• Attachment text extraction stub – return “(attachment text not yet supported)” so GPT can warn users gracefully until implemented.

Once these are in place, the Custom GPT can fulfil “daily / weekly digest”, “search mails containing X”, and “summarise all unread with attachments” scenarios without further breaking API changes.

Let me know which of these endpoints or features you’d like prioritised, and we can start slicing tickets and implementation tasks.