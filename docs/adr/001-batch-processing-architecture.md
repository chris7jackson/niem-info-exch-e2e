# ADR-001: Batch Processing Architecture

## Status
Accepted

## Context

The NIEM Information Exchange system supports multiple batch processing operations:
- **Schema Upload**: Multiple XSD files uploaded together
- **XML Ingestion**: Multiple XML instance documents ingested to Neo4j
- **JSON Ingestion**: Multiple JSON instance documents ingested to Neo4j
- **XML-to-JSON Conversion**: Convert multiple XML files to JSON

Each batch operation spawns external processes (Java-based NIEM tools: CMF, NIEMTran, Schematron) and creates temporary files. Without proper resource management:

**Local Development Issues:**
- Docker containers can be overwhelmed with simultaneous Java subprocess spawns
- Excessive memory consumption on developer machines
- Disk I/O contention from temporary file creation
- Process table exhaustion

**Production Deployment Issues:**
- Need to support both containerized (Docker/Kubernetes) and serverless (Lambda) deployment
- Unpredictable resource usage makes capacity planning difficult
- Cost implications for cloud deployments

**Current State:**
- No consistent concurrency controls across endpoints
- Each operation handles resources independently
- Risk of resource exhaustion with even moderate batch sizes

## Decision

Implement **synchronous batch processing with controlled concurrency** across all batch operations.

### Core Principles

**1. Concurrency Control**
- Use `asyncio.Semaphore` to limit parallel operations
- Configurable via `BATCH_MAX_CONCURRENT_OPERATIONS` (default: 3)
- Prevents resource exhaustion on local machines
- Provides predictable resource usage for cloud deployment

**2. Batch Size Limits** (Operation-Specific)
- **Schema Upload**: Max 50 files (via `BATCH_MAX_SCHEMA_FILES`)
  - NIEM schemas often have 25+ reference XSD files
- **XML/JSON Conversion**: Max 20 files (via `BATCH_MAX_CONVERSION_FILES`)
- **XML/JSON Ingestion**: Max 20 files (via `BATCH_MAX_INGEST_FILES`)
- Returns HTTP 400 if limit exceeded
- Configurable via environment variables for production deployments

**3. Timeout Management**
- Configurable timeout per file via `BATCH_OPERATION_TIMEOUT` (default: 60s)
- Prevents hung processes from blocking batch
- Fails individual files, continues processing others

**4. Error Isolation**
- One file failure does not stop batch processing
- Per-file error details returned in batch result
- Validation errors include line numbers and context

**5. Synchronous Response**
- API waits for all files to complete
- Returns complete batch result in single response
- No job queues, polling, or WebSocket complexity needed

### Implementation Pattern

All batch endpoints follow this handler pattern:

```python
import asyncio
from typing import List
from ..core.config import batch_config

# Shared semaphore for system-wide concurrency control
# Configurable via BATCH_MAX_CONCURRENT_OPERATIONS environment variable
_operation_semaphore = asyncio.Semaphore(batch_config.MAX_CONCURRENT_OPERATIONS)

async def handle_batch_operation(files: List[UploadFile], operation_type: str, ...):
    """Generic batch processing handler"""

    # 1. Validate batch size (operation-specific limits)
    max_files = batch_config.get_batch_limit(operation_type)
    if len(files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum of {max_files} files"
        )

    # 2. Process files with concurrency control
    async def process_single_file(file: UploadFile):
        async with _operation_semaphore:  # Concurrency controlled by config
            try:
                # Set timeout for this operation
                return await asyncio.wait_for(
                    _process_file_logic(file),
                    timeout=batch_config.OPERATION_TIMEOUT
                )
            except asyncio.TimeoutError:
                return _create_error_result(file.filename, "Operation timed out")
            except Exception as e:
                return _create_error_result(file.filename, str(e))

    # 3. Execute all files (semaphore controls concurrency)
    results = await asyncio.gather(*[
        process_single_file(file) for file in files
    ])

    # 4. Return batch summary
    return {
        "files_processed": len(files),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results
    }
```

### Configuration

All batch processing limits are configurable via environment variables for flexibility across different deployment environments.

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BATCH_MAX_CONCURRENT_OPERATIONS` | 3 | Max parallel operations across entire system |
| `BATCH_OPERATION_TIMEOUT` | 60 | Timeout in seconds per individual file |
| `BATCH_MAX_SCHEMA_FILES` | 50 | Max files for schema upload (NIEM often has 25+ refs) |
| `BATCH_MAX_CONVERSION_FILES` | 20 | Max files for XML/JSON conversion |
| `BATCH_MAX_INGEST_FILES` | 20 | Max files for XML/JSON ingestion |

**Example `docker-compose.yml` override for production:**

```yaml
services:
  api:
    environment:
      BATCH_MAX_CONCURRENT_OPERATIONS: 5  # More powerful server
      BATCH_OPERATION_TIMEOUT: 120        # Larger files
      BATCH_MAX_CONVERSION_FILES: 50      # Higher limits
      BATCH_MAX_SCHEMA_FILES: 100         # Large NIEM schemas
```

**Configuration Location:** `api/src/niem_api/core/config.py`

### Applies To

This pattern **MUST** be applied to all batch operations:

| Endpoint | Batch Support | Configurable Limits |
|----------|---------------|---------------------|
| `POST /api/convert/xml-to-json` | ✅ Complete | ✅ Uses `BATCH_MAX_CONVERSION_FILES` |
| `POST /api/ingest/xml` | Partial | ⏳ Add semaphore + config |
| `POST /api/ingest/json` | Partial | ⏳ Add semaphore + config |
| `POST /api/schema/xsd` | Partial | ⏳ Add semaphore + config |

## Consequences

### Positive

✅ **Prevents Resource Exhaustion**: Semaphore limits prevent overwhelming local Docker or developer machines

✅ **Predictable Performance**: Consistent concurrency means predictable resource usage and capacity planning

✅ **Simple Implementation**: Synchronous processing avoids complex job queue infrastructure

✅ **Works Everywhere**: Pattern works in Docker, Kubernetes, and serverless (with appropriate timeouts)

✅ **Error Transparency**: Per-file status and detailed validation errors improve debugging

✅ **Consistent UX**: All batch operations behave the same way across the system

### Negative

❌ **Request Duration**: Large batches (10 files × 60s timeout = 10 minutes max) may exceed typical HTTP timeouts

❌ **No Progress Updates**: Users wait for entire batch to complete (no streaming updates)

❌ **Batch Size Limitation**: 10 files maximum may not suit all use cases

❌ **Sequential Bottlenecks**: Only 3 concurrent operations across entire system

### Mitigation Strategies

For limitations above:
- **HTTP Timeouts**: Batch size limit (10 files) keeps total time reasonable
- **Progress Updates**: Frontend shows "Converting X of Y files..." but no real-time granularity
- **Larger Batches**: See "Future Considerations" for async job queue architecture

## Alternatives Considered

### Alternative 1: No Concurrency Limits (Sequential Processing)

**Approach**: Process files one at a time, completely serially

**Pros**:
- Simplest implementation
- Lowest resource usage
- No concurrency bugs

**Cons**:
- Very slow for batches (10 files × 10s each = 100s total)
- Poor user experience
- Doesn't utilize available resources

**Verdict**: ❌ Rejected - Too slow for acceptable UX

### Alternative 2: Unlimited Parallelism

**Approach**: Process all files simultaneously

**Pros**:
- Fastest possible processing
- Simple implementation (just `asyncio.gather`)

**Cons**:
- Will crash Docker containers with >5 files
- Unpredictable resource usage
- Process/memory exhaustion on local machines

**Verdict**: ❌ Rejected - Unsafe for local development

### Alternative 3: Async Job Queue (Celery + Redis)

**Approach**: Return job ID immediately, process asynchronously, poll for results

**Pros**:
- Handles large batches (100+ files)
- Non-blocking HTTP requests
- Can distribute across workers

**Cons**:
- Significant infrastructure overhead (Redis, workers, monitoring)
- Complex frontend (polling, WebSockets, or long polling)
- Over-engineered for current batch sizes (1-10 files)
- Operational complexity for deployment

**Verdict**: ❌ Rejected for now - Over-engineered for small batches, but see "Future Considerations"

### Alternative 4: Serverless Functions (AWS Lambda per file)

**Approach**: Trigger separate Lambda for each file

**Pros**:
- Infinite scalability
- Pay-per-use
- No resource management needed

**Cons**:
- Vendor lock-in (AWS-specific)
- Cold start latency
- Requires rearchitecting deployment
- Complex state aggregation
- Doesn't work for local Docker development

**Verdict**: ❌ Rejected - Doesn't support local development requirement

### Alternative 5: Stream Processing (Kafka/RabbitMQ)

**Approach**: Stream files through message queue

**Pros**:
- Handles high throughput
- Decoupled architecture

**Cons**:
- Massive infrastructure overhead
- Complex operational requirements
- Total overkill for batch sizes of 1-10 files

**Verdict**: ❌ Rejected - Overengineered

## Future Considerations

### Trigger for Re-evaluation

This decision should be **revisited** when:
- Batch size requirements exceed 50 files
- Request timeout becomes a blocker (users complain about wait times)
- Deployment moves to production cloud with dedicated infrastructure budget

### Recommended Future Architecture: Async Job Queue

If batch requirements grow, migrate to async job processing:

**Architecture**:
```
┌─────────┐      ┌─────────┐      ┌──────────┐      ┌─────────┐
│ Frontend│─────▶│ FastAPI │─────▶│ Job Queue│─────▶│ Workers │
│         │◀─────│         │◀─────│  (Redis) │      │ (Celery)│
└─────────┘      └─────────┘      └──────────┘      └─────────┘
   │                  │                                    │
   │                  │                                    ▼
   │                  │                              ┌──────────┐
   │                  └──────────────────────────────│  Neo4j   │
   │ Poll for results                                │  MinIO   │
   └───────────────────────────────────────────────▶│  etc.    │
                                                     └──────────┘
```

**Flow**:
1. `POST /api/convert/xml-to-json/batch` returns `job_id` immediately
2. Background workers process files asynchronously
3. `GET /api/jobs/{job_id}` polls for status and results
4. Optional: WebSocket for real-time progress updates

**Benefits**:
- Supports large batches (100+ files)
- Non-blocking HTTP requests
- Real-time progress tracking
- Horizontal scaling of workers

**Implementation Options**:
- **Self-hosted**: Celery + Redis (Docker-friendly)
- **AWS**: SQS + Lambda + DynamoDB (serverless)
- **Azure**: Service Bus + Functions + Cosmos DB
- **GCP**: Pub/Sub + Cloud Run + Firestore

**Migration Path**:
1. Create new `/batch` endpoints (keep existing for backward compatibility)
2. Add job status tracking (Redis or database)
3. Deploy Celery workers (or cloud equivalent)
4. Update frontend to poll for results
5. Optional: Add WebSocket support for progress updates

## References

- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Python asyncio Semaphores](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore)
- [Celery Distributed Task Queue](https://docs.celeryq.dev/)
- Issue #33: Improve XML to JSON converter with batch processing

## Related Decisions

- Future ADR: Authentication and authorization strategy
- Future ADR: Cloud deployment architecture
