# Architecture

This is the target architecture. Components are added as they're built.

```mermaid
flowchart LR
    CI[CI job / CLI uploader] --> API
    UI[React UI<br/>triage + chat] -->|OIDC login| API[results-api<br/>FastAPI]
    API --> OBJ[(Object storage<br/>MinIO / S3)]
    API --> PG[(Postgres + pgvector<br/>runs, results, clusters,<br/>signatures, jobs, audit,<br/>chunks, embeddings)]
    API --> GW
    WK[worker<br/>preprocess, check,<br/>cluster, analyse] --> PG
    WK --> OBJ
    WK --> GW[model gateway]
    GW --> CL[Claude<br/>Anthropic API / Bedrock EU]
    GW --> LOC[Local LLM<br/>Ollama / vLLM]
    WK -->|MCP over HTTP| HM[history-mcp<br/>signatures, flakiness,<br/>station health]
    WK -->|MCP over HTTP| TM[ticket-mcp<br/>search, draft]
    WK -->|MCP over HTTP| KM[knowledge-mcp<br/>hybrid search + rerank]
    API -->|MCP over HTTP| KM
    TM --> LEG[mock legacy test-management<br/>and ticket system]
    HM --> PG
    KM --> PG
    ING[ingestion job<br/>parse, OCR, chunk, embed] --> PG
    WK -.traces.-> OBS[Langfuse + OTel]
    API -.metrics.-> PROM[Prometheus / Grafana]
```

## Components

- **results-api (FastAPI):** OIDC login; campaign upload (results XML + log bundles, validated and size-limited); run, cluster and failure views; confirm/correct; ticket drafts; chat endpoint (streaming). Never runs analysis inside a request.
- **CLI / CI uploader:** small Python CLI and a GitHub Actions step that upload a campaign after a test run. Shows how TriageLens plugs into an existing pipeline.
- **worker:** Postgres job queue (`SELECT … FOR UPDATE SKIP LOCKED`); preprocess → deterministic checks → clustering → LLM analysis per cluster → ticket matching → results. Timeouts, retries with backoff, idempotent per run; failures → `Needs review`.
- **log-preprocessing library:** normalisation, key-line extraction, diff against the last passing run, token budgeting. Pure Python, heavily unit-tested, reusable on its own.
- **model gateway (library):** providers for the Anthropic API, Amazon Bedrock and OpenAI-compatible endpoints (Ollama, vLLM); provider/model per task in config; timeouts, retries, token/cost accounting, tracing.
- **history-mcp (MCP, Streamable HTTP):** `match_signatures(evidence)`, `get_test_history(test_id, n)`, `get_last_passing_run(test_id, config)`, `get_station_events(station, time_window)`. All deterministic.
- **ticket-mcp (MCP, Streamable HTTP):** `search_tickets(query, filters)`, `get_ticket(id)`, `draft_ticket(cluster_id)`. Drafts only; creation requires a human action in the UI.
- **mock legacy test-management and ticket system:** deliberately awkward (XML responses, cryptic field names, mixed German/English, paging, occasional 500s and slow responses). Adapter handles mapping, retries and caching.
- **knowledge-mcp (MCP, Streamable HTTP):** `search_documents(query, filters)`: Postgres full-text + pgvector, reciprocal rank fusion, local multilingual cross-encoder reranker; access filter in SQL **before** ranking; returns chunks with document, section and ticket IDs.
- **Ingestion job:** PDF, DOCX, PPTX and one scanned document (layout-aware parser such as Docling, OCR for scans); chunk by section; metadata (doc type, spec number/release, project, access level); local multilingual embeddings (e.g. bge-m3 or multilingual-e5). Idempotent per document version.
- **Postgres + pgvector (single database):** runs, results, clusters, signatures, feedback, jobs, audit log (append-only, hash-chained), chats, chunks with full-text index and embeddings. Read-only DB user for MCP servers.
- **Object storage:** MinIO locally/offline, S3 (encrypted, private) on AWS.
- **React UI (Vite + TypeScript):** run overview grouped by root-cause cluster; cluster detail with evidence lines, log diff, category, confidence, matched tickets, spec references; confirm/correct; ticket draft; chat view with clickable citations.
- **Auth:** Keycloak locally/offline, Cognito on AWS. Roles: `engineer`, `lead`. Per-customer-project access to tickets and device documents.
