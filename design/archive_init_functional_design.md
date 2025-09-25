# NIEM Demo & Proof-of-Concept — Product Requirements & Architecture (v2)

*Last updated: Sep 18, 2025*

---

## 1) Executive Summary

Build a **local-first NIEM demo** showcasing a production-ready pathway. The app lets a user:

1. **Upload & validate an XSD** against **NIEMOpen/OASIS Common Model Format (CMF)** conformance.
2. Upload XML or JSON files (one or many) against the uploaded NIEM-conformant XSD using the official **CMF tool (Java) to validate the XML**, and a **CMF-derived JSON Schema** to validate the JSON files.
3. **Emit events to a Redis Stream** on successful validation; **persist original files** to S3-compatible storage (MinIO).
4. **Stream a worker/consumer** that reads from Redis Streams and **ingests the validated data to Neo4j**.
5. Offer a **reactive web UI** to manage schemas, upload XML/JSON payloads, monitor progress via **Server-Sent Events (SSE)**, reset stores, and **visualize the graph**.

This PoC must be **containerized** for local use (Docker Compose), with a clear runway to **production-grade** deployment.

---

## 2) Goals & Non-Goals

### Goals
* Demonstrate **end-to-end NIEM flow**: XSD → CMF validation → XML/JSON upload → eventing → object storage → graph ingestion → graph visualization.
* Provide a **clean, elegant UI** with progress bars, history, and reset tools.
* Supply **deterministic APIs** and **data contracts** for redis stream messages and persisted artifacts.
* Make it **easy to run locally** (one-command Docker Compose), with **production guidance**.

### Non-Goals
* Full NIEM domain model coverage for every domain (demo focuses on chosen example XSDs).
* Full JSON Schema generation fidelity for every XSD nuance (good-enough mapping for demo, pluggable for extension).
* Enterprise auth integrations beyond OIDC pattern (provide OIDC-ready stubs & config, not bespoke SSO work).

---

## 3) System Overview

### Core Flow
1. **Schema Upload** → Validate XSD against CMF (Java CMF tool in sidecar). Store schema. Generate JSON Schema using CMF converter. Persist metadata + reports.
2. **Data Upload** → Validate XML(s) against active XSD, JSON(s) against JSON Schema. For each valid file:  
   * Write file to **MinIO** (S3).  
   * Append **ingest event** to **Redis Stream** `niem.ingest` with metadata + S3 key.  
3. **Worker/Consumer** → Reads from Redis Stream via **consumer group**, fetches from MinIO, **parses/normalizes**, **upserts** to **Neo4j** using schema-specific mapping spec.  
4. **UI** → Single progress pane (per-file rows + overall), tabs for **Schema** and **Upload**, **basic graph** visualization.

### High-Level Architecture (Logical)
```
+----------------------+         +--------------------+        +-----------------+
|      Web UI          |  REST   |    FastAPI App     |  S3    |      MinIO      |
|  (Next.js/React)     +-------->+ (CMF invoker, API) +------->+  (Object Store) |
|  SSE for progress    |         |  Redis Producer    |        +-----------------+
+-----------+----------+         +---+------------+---+
            |                        |            |
            | SSE/HTTP               | Redis      |
            v                        v            v
       Graph Vis.             +--------------+   +----------------+
        (Neovis.js)           |  Redis       |   |    Neo4j       |
                              |  Streams     |   |    Graph DB    |
                              +------+-------+   +----------------+
                                     |
                                     | Consumer Group
                                     v
                             +---------------+
                             | Ingestor Svc  |
                             |  (FastAPI)    |
                             +---------------+
```

---

## 4) Detailed Requirements

### 4.1 Functional Requirements (FR)

**FR-1. Upload XSD**
* Endpoint: `POST /api/schema/xsd` (multipart). Accept `.xsd` (<= 20 MB).
* Validate with CMF tool for NIEM conformance. On **success**:  
  - Persist to MinIO:  
    ```
    schemas/{schema_id}/schema.xsd
    schemas/{schema_id}/jsonschema.json
    schemas/{schema_id}/cmf_report.json
    ```  
  - Return validation report + schema_id.  
* On **failure**: return structured error report (tool stderr/stdout), retain last valid schema.
* Support multiple stored schemas; one active at a time.  
  - Switch via `POST /api/schema/activate/{schema_id}`.

**FR-2. Read Schema**
* Endpoint: `GET /api/schema` → metadata (active version, uploaded at, converter, version, known gaps).

**FR-3. Upload XML(s)**
* Endpoint: `POST /api/ingest/xml` (multipart, supports many files).  
* For each file:  
  - Validate via CMF tool.  
  - If valid → write original XML to MinIO `niem-incoming/xml/{job_id}/{uuid}_{sha256[:8]}.xml`.  
  - Append ingest event to Redis Stream `niem.ingest` with `content_type: application/xml`.  
  - If invalid → record failure (per-file), return mixed result; do not publish event.  
* UI shows **per-file progress** and **batch overall progress**.

**FR-4. Upload JSON(s)**
* Endpoint: `POST /api/ingest/json` (multipart).  
* Validate against **generated JSON Schema**.  
  - If valid → write JSON to MinIO `niem-incoming/json/{job_id}/{uuid}_{sha256[:8]}.json`.  
  - Append ingest event to Redis Stream `niem.ingest` with `content_type: application/json`.  
  - If invalid → record failure, do not publish event.  

**FR-5. Redis Streams Producer**
* Publish only after MinIO write succeeds.  
* Event includes `schema_id`, `job_id`, trace id, checksum, attempt count.

**FR-6. Redis Streams Consumer → Neo4j Ingest**
* Consumer group: `niem.ingestor`.  
* Retry up to 5x, then route to `niem.dlq`.  
* Mapping: apply per-schema YAML/JSON mapping spec. Auto-create indexes/constraints.  
* Upsert to Neo4j via `MERGE`, with idempotency key `sha256(file_bytes)+schema_id`.

**FR-7. Reset Controls**
* Endpoint: `POST /api/admin/reset` with options: `{ minio, redis, neo4j, schema }`.  
* `dry_run=true` returns counts.  
* Require confirm token to execute.  
* Registry preserved unless `schema=true`.

**FR-8. UI Features**
* Pages: Dashboard, Schema Manager, Data Upload (XML/JSON), Jobs/History, Graph Explorer, Admin/Reset.  
* Progress via SSE (`GET /events/jobs/{job_id}`).  
* Graph visualization with filters, search, depth slider.  
* Retry failed files button on Jobs page.

**FR-9. Audit & Traceability**
* Persist jobs and per-file status (`job_id`, files[], validation, s3_key, stream_id, retries, timings).  
* Endpoints: `GET /api/jobs`, `GET /api/jobs/{id}`.

---

### 4.2 Non-Functional Requirements (NFR)
* Local perf: ~500 XML/minute on dev laptop (50KB avg size).  
* Reliability: idempotent ingestion, at-least-once delivery.  
* Observability: JSON logs (with log rotation), Prometheus metrics, trace_id correlation.  
* Logs: JSON to STDOUT; rotation via Docker `json-file` driver (`max-size: 100m`, `max-file: 5`).  
* Portability: `docker compose up`; production Helm charts.  
* Security (even local): file size caps, XXE disabled, containers run as non-root.

---

## 5) Tech Stack & Components
* **Frontend**: Next.js + React, Tailwind. SSE for progress. Graph vis via Neovis.js.  
* **API**: FastAPI, Python 3.12, uvicorn. Invokes CMF tool (sidecar).  
* **CMF Tool**: Official NIEMOpen/OASIS Java executable in sidecar container.  
* **Eventing**: Redis Streams.  
* **Object Store**: MinIO.  
* **Graph DB**: Neo4j 5.x (+APOC).  
* **Orchestration**: Docker Compose (local).  
* **Observability**: JSON logs (with rotation), Prometheus metrics.  

---

## 6) API Design (Selected)

> **All write endpoints require `Authorization: Bearer <DEV_TOKEN>` in the PoC.**

**Schema**
- `POST /api/schema/xsd` → `{ schema_id, cmf_report, is_active }`
- `POST /api/schema/activate/{schema_id}`
- `GET /api/schema`

**Ingest**
- `POST /api/ingest/xml` → per-file results; append to Redis on success.  
- `POST /api/ingest/json` → per-file results; append to Redis on success.  

**Jobs/Admin**
- `GET /api/jobs`, `GET /api/jobs/{id}`  
- `POST /api/admin/reset`  

**Realtime (SSE)**
- `GET /events/jobs/{job_id}` → emits `progress` and `complete` events.  
- Supports `Last-Event-ID`.  

---

## 7) Data Contracts

### 7.1 Ingest Event (Redis Streams payload)
```json
{
  "event_id": "uuid",
  "event_ts": "2025-09-18T00:00:00Z",
  "schema_id": "string",
  "content_type": "application/xml | application/json",
  "s3_bucket": "niem-incoming",
  "s3_key": "string",
  "checksum": "sha256-...",
  "attempt": 1,
  "validation": {
    "tool": "cmf",
    "status": "valid | invalid",
    "report_ref": "s3://niem-reports/<id>.json"
  },
  "source": { "ip": "string", "user": "string|sub" },
  "job_id": "string"
}
```

---

## 8) Observability & Benchmarks
* Logs: structured JSON with trace_id, job_id, file_id, schema_id.  
* Rotation: enforced at container level via Docker logging options.  
  ```yaml
  logging:
    driver: "json-file"
    options:
      max-size: "100m"
      max-file: "5"
  ```
* Metrics:  
  - `niem_validate_duration_seconds`  
  - `niem_ingest_events_total`  
  - `niem_stream_lag_entries`  
  - `niem_minio_write_failures_total`  
  - `niem_neo4j_tx_duration_seconds`  
* Health endpoints: `/healthz`, `/readyz`.  
* Benchmark: synthetic dataset generator + benchmark script in `tools/`.  

---
