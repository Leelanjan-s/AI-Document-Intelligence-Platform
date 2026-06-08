# API Design & Contracts - AI Document Intelligence Platform

This document describes the REST API contracts, path patterns, query schemas, and request/response payloads.

All endpoints are prefixed with `/api/v1`. Authentication is enforced via JWT access tokens passed inside the HTTP `Authorization: Bearer <token>` header, or securely through client-side cookies for web application flows.

---

## 1. Authentication Router (`/auth`)

### A. Login User
Authenticates a user and issues Access and Refresh tokens.

- **URL**: `/api/v1/auth/login`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "email": "test@acme.com",
    "password": "test1234"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": "77777777-7777-7777-7777-777777777777",
      "email": "test@acme.com",
      "role": "admin",
      "organization_id": "00000000-0000-0000-0000-000000000000",
      "is_active": true
    }
  }
  ```
- **Response (401 Unauthorized)**:
  ```json
  {
    "detail": "Incorrect email or password"
  }
  ```

---

### B. Refresh Access Token
Issues a new access token using a valid refresh token.

- **URL**: `/api/v1/auth/refresh`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```

---

## 2. Document Processing Router (`/documents`)

### A. Create Presigned Upload URL
Returns a secure URL for the client to upload files directly to MinIO/S3 object storage, avoiding backend network choke.

- **URL**: `/api/v1/documents/upload`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "filename": "invoice_123.pdf",
    "file_size": 245000,
    "mime_type": "application/pdf"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "document_id": "88888888-8888-8888-8888-888888888888",
    "upload_url": "http://localhost:9000/documents-bucket/raw/88888888?Signature=...",
    "storage_path": "raw/88888888-8888-8888-8888-888888888888"
  }
  ```

---

### B. Fetch Document List
Retrieves a paginated list of documents with metadata. Filters by status and type.

- **URL**: `/api/v1/documents`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**:
  - `status` (Optional): Filter by status (`uploaded`, `processing`, `review_needed`, `completed`, `failed`).
  - `skip` (Default: 0): Pagination offset.
  - `limit` (Default: 20): Maximum records.
- **Response (200 OK)**:
  ```json
  [
    {
      "id": "88888888-8888-8888-8888-888888888888",
      "name": "invoice_123.pdf",
      "status": "review_needed",
      "file_size": 245000,
      "mime_type": "application/pdf",
      "confidence_score": 0.76,
      "created_at": "2026-06-06T12:00:00Z",
      "updated_at": "2026-06-06T12:01:05Z",
      "doc_type_id": "11111111-1111-1111-1111-111111111111"
    }
  ]
  ```

---

### C. Fetch Extracted Data
Retrieves parsed, structured fields and validation logs for a document.

- **URL**: `/api/v1/documents/{id}/result`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**:
  ```json
  {
    "document_id": "88888888-8888-8888-8888-888888888888",
    "data": {
      "invoice_number": "INV-2026-004",
      "invoice_date": "2026-06-01",
      "total_amount": 1250.50
    },
    "confidence_scores": {
      "invoice_number": 0.98,
      "invoice_date": 0.95,
      "total_amount": 0.65
    },
    "validation_errors": [
      {
        "field": "total_amount",
        "error": "Total amount does not match sum of items",
        "severity": "warning"
      }
    ]
  }
  ```

---

### D. Human Review / Audit Submission
Allows a reviewer to submit corrected data structures, moving a document out of the review queue.

- **URL**: `/api/v1/documents/{id}/review`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "updated_data": {
      "invoice_number": "INV-2026-004",
      "invoice_date": "2026-06-01",
      "total_amount": 1250.00
    },
    "action": "edited",
    "comments": "Fixed total amount value to match item lines"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "message": "Review submitted successfully",
    "document_status": "completed"
  }
  ```

---

## 3. Analytics & Metrics Router (`/metrics`)

### A. Fetch Dashboard Metrics
Aggregates processing throughput, latency metrics, and agent token costs.

- **URL**: `/api/v1/metrics`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**:
  ```json
  {
    "volume": {
      "total": 150,
      "completed": 120,
      "review_needed": 22,
      "processing": 5,
      "failed": 3
    },
    "latency": {
      "avg_ms": 4820,
      "p95_ms": 7890
    },
    "costs": {
      "total_tokens": 1245000,
      "total_usd": 15.34
    },
    "agent_performance": [
      {
        "agent_name": "ocr_agent",
        "avg_latency_ms": 1200,
        "success_rate": 0.99
      },
      {
        "agent_name": "extraction_agent",
        "avg_latency_ms": 2300,
        "success_rate": 0.96
      }
    ]
  }
  ```

---

## 4. Utility Router (`/health`)

### A. API Health Check
Validates health states of backend databases and caching adapters.

- **URL**: `/api/v1/health`
- **Method**: `GET`
- **Response (200 OK)**:
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "storage": "connected"
  }
  ```
- **Response (503 Service Unavailable)**:
  ```json
  {
    "status": "unhealthy",
    "database": "disconnected",
    "redis": "connected",
    "storage": "connected"
  }
  ```
