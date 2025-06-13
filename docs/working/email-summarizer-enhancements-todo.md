# Outlook Email Summarizer – Enhancements TODO

> **Filename:** `docs/working/email-summarizer-enhancements-todo.md`
> **Objective:** Extend the MVP single-message summarizer into a production-grade, multi-message RAG-enabled summarisation service consumable by Custom GPTs.

---

## 1 · Technical Summary

### 1.1 Problem Statement
The current API supports only `GET /summarize?msg_id=<id>` which returns a TL;DR for one Outlook message. Business requirements now include:

* Daily / weekly digest generation across many emails.
* Natural-language Q&A or regex search over mailboxes (RAG).
* Attachment text extraction & inclusion in summaries / answers.
* Bulk summarisation (list of message IDs) with caching & pagination.
* Async job orchestration for long-running tasks.

### 1.2 System Context
```
FastAPI (summarizer-api)
 ├─ app/
 │   ├─ main.py               ← APIRouter registration hub
 │   ├─ services.py           ← Business logic (LLM summarisation)
 │   ├─ auth.py               ← MSAL graph token helper
 │   ├─ models.py             ← Pydantic DTOs
 │   └─ …
 ├─ Redis (cache + job queue)
 ├─ Microsoft Graph API       ← e-mail data source & attachment blobs
 └─ pgvector (PostgreSQL)     ← vector store for RAG (to-be-added)
```
Dependencies: MSAL, LangChain, Redis, OpenAI/Ollama, future `pgvector` & embeddings lib.

### 1.3 Current vs Expected Behaviour
| Aspect | Current (MVP) | Expected (Post-enhancement) |
|--------|---------------|-----------------------------|
| Fetch granularity | Single message by ID | List, search, or date-range; attachments accessible |
| Summarisation | Map-reduce over one body | Digest over N bodies; per-msg summaries + overall digest |
| RAG / Q&A | ❌ None | Vector store, `/rag/query` endpoint, cited answers |
| Attachments | ❌ Ignored | MIME attachment fetch, type-specific text extraction |
| Long jobs | ❌ Blocking HTTP | Async job submission + polling |
| OpenAPI spec | Single op | Multiple operations, grouped by domain |

---

## 2 · Hierarchical Task Breakdown

### 2.1 Email Data Access Layer
- [ ] **Create repository** `app/graph/email_repository.py`
  - Implements:
    - `async get_email(msg_id: str) -> EmailEnvelope`
    - `async list_emails(filters: EmailFilter, paging: Paging) -> list[EmailEnvelope]`
    - `async get_attachment(msg_id: str, att_id: str, *, as_text: bool)`
  - Rationale: centralise Graph calls; enable batching.
  - Files:
    - `app/graph/email_repository.py` *(new)*
    - `app/__init__.py` (export repository)
  - Runtime: honour Graph `$top` ≤ 100; exponential back-off on 429.
  - Validation: unit-test with `responses` mocking Graph.

### 2.2 Refactor Existing Service
- [ ] **Update** `app/services.py`
  - Replace direct Graph calls → repository.
  - Extract `summarise_documents(docs: list[str])` util.
  - Edge cases: zero-length body, HTML artifacts.
  - Depends on Task 2.1.

### 2.3 Email Endpoints
- [ ] **Router** `app/routes/emails.py`
  - `GET /emails` (search/list)
  - `GET /emails/{msg_id}` (full)
  - `GET /emails/{msg_id}/attachments/{att_id}`
  - Files:
    - `app/routes/emails.py` *(new)*
    - `app/main.py` (include_router)
  - Validation: FastAPI docs render; 2xx / 4xx paths covered in tests.

### 2.4 Bulk & Digest Summaries
- [ ] **Extend service**
  - `summarise_bulk(ids: list[str], mode: str) -> DigestResult`
- [ ] **Router** `app/routes/summaries.py`
  - `POST /summaries` (bulk)
  - `GET /summaries/daily` & `/weekly`
  - Cache digest under composite key `range|filters`.
  - Runtime: may spawn background task if `len(ids) > 50`.

### 2.5 Vector Store & RAG
- [ ] **DB migration** `migrations/20240611_email_embeddings.sql`
  - Table `email_embeddings(id TEXT PRIMARY KEY, embedding VECTOR(1536), metadata JSONB)`
- [ ] **Embedding service** `app/vector/embedding_service.py`
  - Uses `OpenAIEmbeddings` / `ollama-embed`.
- [ ] **Ingestion worker** `workers/ingest_emails.py`
  - CLI `python workers/ingest_emails.py --start YYYY-MM-DD --end …`.
- [ ] **Endpoint** `POST /rag/ingest` → queue job.
- [ ] **Endpoint** `POST /rag/query` – semantic search + answer w/ sources.
  - Runtime: limit `top_k <= 15`; chunk dedup.
  - Validation: unit test uses fake vectors, expect ranked ids.

### 2.6 Async Job Framework
- [ ] **Queue module** `app/jobs/queue.py` using Redis lists or RQ.
- [ ] **Job model** `app/models.py::JobStatus`
- [ ] **Endpoint** `GET /jobs/{id}`
  - Validation: enqueue-run-poll cycle in tests.

### 2.7 Attachment Extraction
- [ ] **Utility** `app/utils/attachment_extract.py`
  - MIME type switch: PDF→`pdfplumber`, DOCX→`python-docx`, fallback→`textract`.
- [ ] Integrate in repository so bodies include attachment text delimiter `\n--- Attachment: <name> ---\n`.
- Runtime: skip >5 MB, return warning.

### 2.8 OpenAPI & GPT Action
- [ ] **Update** `openapi.yaml` with new paths, schemas.
- [ ] Provide `docs/examples/system-prompt.md` with usage.

### 2.9 Tests & CI
- [ ] Add **Vitest** (if needed) or `pytest` suites under `tests/`:
  - repository, summariser, vector search, endpoints.
- [ ] GitHub Actions workflow `/.github/workflows/ci.yml` (lint + tests).

### 2.10 Docs & README
- [ ] Expand `README.md` sections (bulk, RAG, jobs).
- [ ] Add architecture diagram update.

---

## 3 · Implementation Notes

* **Attachment text extraction** can be slow; consider async download + extract pipeline or caching extracted text in Redis keyed by `att_id|hash`.
* **Vector store choice**: pgvector keeps single-instance simplicity but inflates DB image; alternative is Chroma in-proc. Confirm with DevOps.
* **Job queue**: Lightweight `BackgroundTasks` may suffice for ≤1k emails; otherwise RQ or Celery (already depending on Redis) scales better.
* **OpenAPI versioning**: add `/v1` prefix now to avoid breaking future consumers.
* **Security**: ensure attachment download uses Graph pre-auth URLs; DO NOT log raw attachment content.
* **Rate limits**: Graph has 10k requests/10 min per app; bulk endpoints must batch (`/v1/$batch`).

> **Developer checkpoints:**
> 1. Clarify maximum mailbox size expectations (embedding cost).
> 2. Decide on persistence for async job metadata (Redis vs PostgreSQL).
> 3. Confirm licensing if using `textract`/`tika` jars in Docker (size impact). 