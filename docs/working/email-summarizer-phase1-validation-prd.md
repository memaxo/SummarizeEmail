# Outlook Email Summarizer – **Phase 1 PRD**

> **Filename:** `docs/working/email-summarizer-phase1-validation-prd.md`
> **Goal:** Validate the Phase-0 MVP (single-email summariser) in a realistic environment, ensure it meets functional & non-functional requirements, and reach production-readiness sign-off before Phase-2 feature work begins.

---

## 1 · Technical Summary

### 1.1 Problem Statement
We delivered a scaffold (Phase-0) that can summarise a single Outlook email via `GET /summarize?msg_id=<id>`.  Before we invest in Phase-2 expansion, we must prove that:

1.  The endpoint consistently returns accurate TL;DRs for diverse email formats (plain-text, HTML, long threads).
2.  The service is stable under expected load and respects rate limits (Graph, OpenAI).
3.  Security, error handling, logging and Ops hooks (health, metrics) comply with internal SRE requirements.
4.  The OpenAPI action integrates smoothly with a test Custom GPT, usable by a pilot user group.

### 1.2 System Context
- **Affected code:** `app/main.py`, `app/services.py`, `app/auth.py`, Docker & Compose, `openapi.yaml`.
- **External dependencies:** Microsoft Graph, OpenAI or Ollama, Redis.
- **Stake-holders:** Product, SecOps (data residency), SRE, Pilot users.

### 1.3 Current vs Expected Behaviour
| Dimension           | Current MVP (built)                                       | Expected after Phase 1 validation                               |
|---------------------|-----------------------------------------------------------|-----------------------------------------------------------------|
| Accuracy            | Unverified against ground-truth                           | ≥ 90 % "useful" rate (pilot survey)                              |
| HTTP Stability      | Happy-path tested locally                                 | 99.9 % success in soak-test (1 req/s for 2h)                     |
| Latency (OpenAI)    | ~1.5 s median, unmeasured p95                             | p95 ≤ 5 s for ≤ 4 kB emails                                      |
| Security headers    | Defaults (FastAPI)                                        | CSP + HSTS + Helmet in place                                    |
| Logs                | Basic `logging`                                           | Structured JSON, request ID correlation                          |
| OpenAPI ↔ GPT flow  | Manual                        | GPT builder auto-detects action, return flow works for 3 scenarios |

---

## 2 · Validation & Testing Task Breakdown

### 2.1 Functional Accuracy Tests
- [ ] **Golden-set corpus** `tests/data/golden/` (20 emails: HTML, marketing, thread, attachment stub).
  - Rationale: deterministic evaluation.
  - Files: `tests/data/golden/*.eml` (new), `tests/test_accuracy.py` (new).
  - Success metric: ≥ 18/20 summaries rated "good" by rubric.
- [ ] **Rubric script** `tests/eval/rubric.py` using simple heuristics + manual checklist table.

### 2.2 API Unit- & Integration-Tests (pytest)
- [ ] Mock Graph with `responses` to serve fixture JSON.
- [ ] Mock OpenAI with `pytest-httpserver` returning canned completions.
- [ ] Cover:
  - `200` happy path
  - `404` missing mail
  - `502` Graph failure passthrough
  - Redis cache hit path
  - Rate-limit decorator returns `429`
- Runtime: tests run under 30 s.

### 2.3 Load & Soak Testing
- [ ] **Locust script** `tests/load/locustfile.py`
  - 1 req/s ➜ 100 simulated users ➜ 15 min ramp ➜ 2 h plateau.
  - Generate random GUIDs but stub Graph.
- [ ] Record p50/p95 latency to `results/loadtest-<date>.json`.
- Validation: p95 ≤ 5 s, error rate ≤ 0.1 %.

### 2.4 Security & Compliance
- [ ] **Static scan** using Bandit (`bandit -r app/`).
- [ ] **Headers middleware** `app/middleware/security.py` ensures HSTS, CSP, X-Content-Type.
- [ ] Pen-test checklist: no PII in logs, 3 retry lockout on token failure.

### 2.5 Observability
- [ ] **Structured logging** via `loguru` or `structlog`; add `request_id` to each log entry.
- [ ] Add `/metrics` Prometheus endpoint via `prometheus-fastapi-instrumentator`.
- [ ] Update `docker-compose.yml` to expose port `9100` for metrics.

### 2.6 Deployment Validation
- [ ] Build pipeline GitHub Actions `ci.yml` (lint + tests + docker build).
- [ ] Deploy to staging (Azure Container Apps) via `cd.yml`; health check passes.
- [ ] Run smoke tests against staging.

### 2.7 GPT Action Integration Tests
- [ ] Publish API with ngrok, import `openapi.yaml` in GPT builder.
- [ ] Test 3 scenarios:
  1. "Summarise email <ID>"
  2. "What's the gist of this message?" (same ID)
  3. Error path (ID typo) – GPT explains failure.
- [ ] Capture screen-recordings for Product demo.

---

## 3 · Acceptance Criteria
| # | Criterion | Validation Method |
|---|-----------|-------------------|
| 1 | Functional accuracy ≥ 90 % | Golden-set rubric |
| 2 | p95 latency ≤ 5 s @ 1 req/s | Locust report |
| 3 | 0 critical Bandit findings | CI scan |
| 4 | Structured logs with `request_id` observed in Cloud logs | Manual check |
| 5 | GPT Action performs end-to-end in pilot session | UX demo recording |

---

## 4 · Dependencies & Risks
* **OpenAI rate-limit** – may throttle during soak; mitigate with mock for load.
* **Graph throttling** – integration tests use stub; manual pilot uses low volume.
* **Latency variance** on Ollama vs OpenAI – ensure separate baselines.

---

## 5 · Implementation Notes & Open Questions
* Decide whether to adopt `pytest-asyncio` or keep sync tests with `httpx.AsyncClient`.
* Do we store golden-summaries in repo (risk of private data) or synthetic mails only?
* Metrics stack (Prometheus + Grafana) already exists in org – need scrape config.
* Pilot group size & feedback capture mechanism (Google Form vs internal tool?). 