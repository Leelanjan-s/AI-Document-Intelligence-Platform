# Advanced Applied AI Engineering: Interview Preparation Guide
*Target Role: Applied AI Engineer (Bang Bangalore)*
*Audience: 20+ Years Experience Technical Architect / AI Developer*

---

## 1. Executive Summary: Why This Project?

To stand out as a candidate with **3–5 years of experience** when interviewing with a **20+ years experience AI Architect**, you cannot simply talk about using basic wrappers. You must discuss **system design, design patterns, failure domains, scalability bottlenecks, cost tracking, and architectural trade-offs**.

This **Document Intelligence Platform** was specifically built to map 100% to the Pacewisdom Job Description:
* **Agentic AI Pipelines:** Implemented as a modular, graph-based state machine using **LangGraph** (OCR ➔ Classification ➔ Extraction ➔ Validation ➔ Confidence).
* **Schema-Driven Data System:** Adapts to new document types through database configuration (dynamic JSON schemas), avoiding code rewrites.
* **LLM Provider Optimization:** Implements structured Outputs (JSON schema enforcement), prompt versioning, and token-level cost tracking.
* **Workflow Orchestration:** Demonstrates async event processing with PostgreSQL state-saving (with an easy migration path to **Temporal**).
* **Decoupled Architecture:** Features S3/MinIO presigned uploads, Redis cache blacklisting, FastAPI async sessions, and a Next.js 15 light-theme UI.

---

## 2. Business Purpose: Who is it useful for?

Manual document processing is a major bottleneck in enterprises:
* **Problem:** Invoices, receipts, legal contracts, and bank statements arrive in unstructured formats (PDFs, scans, images). Standard OCR tools output raw text, leaving data parsing to human typing, which is slow, expensive, and error-prone.
* **Solution:** This platform automates the extraction of unstructured files into clean, schema-validated database records, introducing **Human-in-the-Loop (HITL)** only when confidence scores fall below **80%**.
* **Impact:** Reduces processing latencies from hours to seconds and saves thousands of manual data-entry hours, making it highly useful for Accounts Payable, Procurement, and Auditing divisions.

---

## 3. End-to-End System Execution Flow

When explaining the project in your interview, describe it as a **6-stage transactional flow**:

```
[Upload Phase] ➔ [Ingestion Phase] ➔ [Agent DAG Phase] ➔ [Routing Phase] ➔ [HITL Queue] ➔ [Analytics]
```

1. **Direct Upload (Client ➔ S3):** The Next.js client requests a presigned upload URL from FastAPI, then uploads the document directly to MinIO S3. This protects backend memory from buffering large files.
2. **Async Task Spawn:** The client notifies FastAPI of upload completion. The API immediately spawns an async background worker running the orchestrator and returns `202 Accepted` to the client.
3. **OCR Processing:** The OCR node pulls the document, runs Tesseract OCR, and defaults to **Multimodal LLM fallback** (base64 image extraction) if local binaries fail.
4. **Dynamic Schema Extraction:** The classification node maps the text to a database document type (e.g. Invoice). The extraction node fetches its dynamic JSON schema, compiles structural instructions, and leverages LLM Structured Output to extract structured JSON keys.
5. **Programmatic Validation & Scoring:** The validation node runs arithmetic validations (e.g. `items.sum() == total`). The confidence node calculates a score based on validation outcomes and LLM log probabilities.
6. **Decision & persistence:** 
   * **Confidence $\ge$ 80%:** Automatically marked as `completed` and saved.
   * **Confidence < 80%:** Sent to the `review_needed` queue for human review. Once reviewed, changes are persisted, and the action is logged.

---

## 4. Deep-Dive Architecture & Trade-Offs (To Impress a 20-Yr Developer)

Be prepared to answer these deep questions in your interview:

### Q1: Why did you choose LangGraph instead of a linear Python pipeline?
> **Answer:** 
> "A linear pipeline (Chain) is fragile. If the validation node catches a total sum mismatch, a linear pipeline fails. With LangGraph, we can introduce **cycles and feedback loops**. We can route the validation failure message *back* to the extraction node as a new prompt, instructing the LLM to correct the specific field using the validation error context. This self-healing architecture drastically reduces human intervention."

### Q2: Why is the database schema designed as "Schema-Driven"?
> **Answer:** 
> "If a company introduces a new document type (e.g., 'Purchase Order'), traditional extraction pipelines require a developer to write a new Pydantic schema class, recompile the app, and redeploy. 
> In our platform, we designed the system to be **schema-driven**. Document schemas are stored dynamically in the `document_types` database table as standard JSON schemas. The orchestrator fetches the schema at runtime and dynamically compiles the structured LLM output parameters. The system scales to support new document structures instantly via simple DB configuration."

### Q3: Why did you implement presigned S3 URLs instead of uploading directly to the backend?
> **Answer:** 
> "Uploading files directly to a FastAPI server blocks ASGI workers and consumes server RAM during transmission, exposing the API to thread starvation under high upload volumes.
> By implementing **presigned URLs**, the FastAPI backend acts purely as a metadata coordinator. The client uploads the file directly to the S3 bucket (MinIO). This architecture keeps our API layer lightweight, stateless, and horizontally scalable."

### Q4: How do you handle workflow orchestration and durability?
> **Answer:** 
> "For our implementation, we wrapped the LangGraph execution in an async Python worker that records states in PostgreSQL (`workflow_runs` and `agent_executions`) at every step. 
> If we scale to millions of document processes daily, we can transition from standard Python background tasks to **Temporal**. Temporal handles state persistence and retries out-of-the-box. Our code's modular node layout makes this migration straightforward."

### Q5: How do you control AI cost and token consumption?
> **Answer:** 
> "We instrumented every agent node execution to retrieve token metrics from LLM responses. We log the prompt tokens, completion tokens, model name, and cost to a `token_usage` table. This allows organizations to track costs per user, per document, and per department in real-time, preventing billing surprises."

### Q6: How is the testing stack isolated?
> **Answer:** 
> "We override the database session maker globally in our `conftest.py` setup to use an in-memory SQLite database (`aiosqlite`). This ensures that unit tests run fast, are fully isolated, require zero external docker databases, and clean themselves up automatically."
