# Database Design - AI Document Intelligence Platform

This document describes the schema design, tables, data types, indexes, and relationships in the relational database model of the platform.

The schema is built using SQLAlchemy 2.0. It is fully compatible with **PostgreSQL** (production) and **SQLite** (testing/local development) by utilizing abstract JSON types and UUID representations.

---

## 1. Entity Relationship Overview

The database design centers around the tenant structure (`organizations`) and the execution state of documents through the LangGraph agents.

```
       [organizations]
        /      |      \
       /       |       \
[users]  [document_types] [documents]
   |          |              |
   |          |      [workflow_runs] --- [agent_executions]
   |          |              |
   |          |      [extracted_data]
   |          |              |
   +-----+----+------+-------+
         |           |
      [reviews]  [token_usage]
```

---

## 2. Table Specifications

### A. `organizations`
Represents the core multi-tenant boundary. All users, documents, and dynamic schemas belong to an organization.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `name` | `VARCHAR(255)` | Unique, Not Null, Indexed | Unique organization identifier. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Account creation timestamp. |
| `updated_at` | `TIMESTAMP` | Default: UTC Now, On Update | Auto-updated modification time. |

---

### B. `users`
Represents user accounts, access roles, and tenant mapping.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `organization_id` | `UUID` | Foreign Key (`organizations.id`), Nullable | Tenant identification. Nullable if platform admin. |
| `email` | `VARCHAR(255)` | Unique, Not Null, Indexed | Login identifier. |
| `hashed_password`| `VARCHAR(255)` | Not Null | Hashed password. |
| `role` | `VARCHAR(50)` | Default: 'user' | Access control level (`admin`, `reviewer`, `user`). |
| `is_active` | `BOOLEAN` | Default: `True` | Account state flag. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Account creation timestamp. |
| `updated_at` | `TIMESTAMP` | Default: UTC Now | Account update timestamp. |

---

### C. `document_types`
Stores custom document parsing schemas defined dynamically by administrators.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `organization_id` | `UUID` | Foreign Key (`organizations.id`), Cascade | Owner organization. |
| `name` | `VARCHAR(100)` | Not Null | Name of the type (e.g. "Invoice"). |
| `description` | `VARCHAR(500)` | Nullable | Descriptive explanation. |
| `schema_definition`| `JSON` | Not Null | JSON schema detailing fields, types, and flags. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Schema creation timestamp. |
| `updated_at` | `TIMESTAMP` | Default: UTC Now | Schema update timestamp. |

*Schema Definition Example:*
```json
{
  "fields": [
    {"name": "invoice_number", "type": "string", "required": true},
    {"name": "invoice_date", "type": "string", "required": true},
    {"name": "total_amount", "type": "number", "required": true}
  ]
}
```

---

### D. `documents`
Stores metadata and status of uploaded files.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `organization_id` | `UUID` | Foreign Key (`organizations.id`), Set Null | Tenant identifier. |
| `user_id` | `UUID` | Foreign Key (`users.id`), Set Null | Uploading user identifier. |
| `doc_type_id` | `UUID` | Foreign Key (`document_types.id`), Set Null | Mapped classification template. |
| `name` | `VARCHAR(255)` | Not Null | Original file name. |
| `storage_path` | `VARCHAR(512)` | Not Null | S3 URI (e.g., `raw/invoices/doc_id.pdf`). |
| `status` | `VARCHAR(50)` | Default: 'uploaded' | State (`uploaded`, `processing`, `review_needed`, `completed`, `failed`). |
| `file_size` | `INTEGER` | Not Null | Size in bytes. |
| `mime_type` | `VARCHAR(100)` | Not Null | File type (e.g., `application/pdf`). |
| `confidence_score`| `FLOAT` | Nullable | Combined parsing accuracy metric. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Upload timestamp. |
| `updated_at` | `TIMESTAMP` | Default: UTC Now | Update timestamp. |

---

### E. `workflow_runs`
Tracks active and historical executions of the LangGraph workflow.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `document_id` | `UUID` | Foreign Key (`documents.id`), Cascade | Target document identifier. |
| `status` | `VARCHAR(50)` | Default: 'running' | Run state (`running`, `completed`, `failed`, `review_needed`). |
| `error_message` | `VARCHAR(1000)`| Nullable | Failure stack or error explanation. |
| `current_step` | `VARCHAR(100)` | Nullable | Current active agent node. |
| `started_at` | `TIMESTAMP` | Default: UTC Now | Execution start time. |
| `completed_at` | `TIMESTAMP` | Nullable | Execution end time. |

---

### F. `agent_executions`
Granular instrumentation detailing individual agent performance inside a workflow run.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `workflow_run_id` | `UUID` | Foreign Key (`workflow_runs.id`), Cascade | Parent workflow run. |
| `agent_name` | `VARCHAR(100)` | Not Null | Name (`ocr_agent`, `classification_agent`, etc.). |
| `status` | `VARCHAR(50)` | Not Null | Outcome (`success`, `failed`). |
| `input_data` | `JSON` | Nullable | Payload ingested by the agent node. |
| `output_data` | `JSON` | Nullable | Payload returned by the agent node. |
| `latency_ms` | `INTEGER` | Default: `0` | Execution latency in milliseconds. |
| `token_usage` | `JSON` | Nullable | Prompt/completion tokens, pricing metrics. |
| `error_message` | `VARCHAR(1000)`| Nullable | Exception details if failed. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Ingestion timestamp. |

---

### G. `extracted_data`
Houses the final structured data output after agent processing.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `document_id` | `UUID` | Foreign Key (`documents.id`), Cascade, Unique | Owner document. |
| `data` | `JSON` | Not Null | Structured key-value outputs. |
| `confidence_scores`| `JSON` | Nullable | Field-level prediction metrics. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Completion timestamp. |
| `updated_at` | `TIMESTAMP` | Default: UTC Now | Update timestamp. |

---

### H. `reviews`
Audit trail documenting corrections made by human reviewers.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `document_id` | `UUID` | Foreign Key (`documents.id`), Cascade | Owner document. |
| `reviewer_id` | `UUID` | Foreign Key (`users.id`), Cascade | Auditing user. |
| `previous_data` | `JSON` | Nullable | Extracted structure before audit. |
| `updated_data` | `JSON` | Not Null | Extracted structure post audit. |
| `action` | `VARCHAR(50)` | Not Null | Status (`accepted`, `rejected`, `edited`). |
| `comments` | `VARCHAR(500)` | Nullable | Reviewer annotations. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Review timestamp. |

---

### I. `audit_logs`
System-wide security auditing capturing access control details.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `organization_id` | `UUID` | Foreign Key (`organizations.id`), Set Null | Tenant identifier. |
| `user_id` | `UUID` | Foreign Key (`users.id`), Set Null | Performing user identifier. |
| `action` | `VARCHAR(255)` | Not Null | Log action (e.g. `document.review`). |
| `entity_type` | `VARCHAR(100)` | Not Null | Affected module type (`document`, `user`). |
| `entity_id` | `UUID` | Nullable | ID of target entity. |
| `action_metadata` | `JSON` | Nullable | Details (e.g. client IP, modified fields). |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Event timestamp. |

---

### J. `prompt_versions`
Enables dynamic prompt version management for LLM performance tweaking without code deploys.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `agent_name` | `VARCHAR(100)` | Not Null, Indexed | Targeted agent (`extraction_agent`, etc.). |
| `version` | `INTEGER` | Not Null | Incremental version number. |
| `system_prompt` | `VARCHAR(2000)`| Not Null | System instruction block. |
| `user_prompt_template`| `VARCHAR(2000)`| Not Null | User instruction block template. |
| `is_active` | `BOOLEAN` | Default: `True` | Active version flag. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Version creation timestamp. |

---

### K. `token_usage`
Instruments prompt, completion, and financial cost tracking per transaction.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Auto-generated UUIDv4. |
| `organization_id` | `UUID` | Foreign Key (`organizations.id`), Set Null | Tenant identifier. |
| `user_id` | `UUID` | Foreign Key (`users.id`), Set Null | User context. |
| `document_id` | `UUID` | Foreign Key (`documents.id`), Set Null | Target document context. |
| `model_name` | `VARCHAR(100)` | Not Null | LLM Model (e.g. `gpt-4o-mini`). |
| `prompt_tokens` | `INTEGER` | Default: `0` | Ingested token count. |
| `completion_tokens`| `INTEGER` | Default: `0` | Output token count. |
| `cost` | `FLOAT` | Default: `0.0` | Transaction cost in USD. |
| `created_at` | `TIMESTAMP` | Default: UTC Now | Ingestion timestamp. |

---

## 3. Indexing & Optimization Strategy

To maintain sub-second retrieval speeds under heavy scale, database tables include indexes on highly queried columns:
1. **Tenant Filtering**: `documents(organization_id)`, `users(organization_id)`, and `document_types(organization_id)` to prevent tenant cross-contamination.
2. **Searchable Columns**: Unique constraints and BTREE indexes on `users(email)` and `organizations(name)`.
3. **Queue Sorting**: Composite index on `documents(status, created_at)` to query documents pending review in chronological order rapidly.
4. **Prompt Retrieval**: Index on `prompt_versions(agent_name, is_active)` to fetch active system instructions instantly.
