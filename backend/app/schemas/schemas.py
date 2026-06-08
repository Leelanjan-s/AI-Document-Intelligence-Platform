from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# Authentication
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    organization_id: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut

class TokenRefreshRequest(BaseModel):
    refresh_token: Optional[str] = None

# Document Types
class DocumentTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    schema_definition: Dict[str, Any]
    
    class Config:
        from_attributes = True

# Documents
class DocumentOut(BaseModel):
    id: uuid.UUID
    name: str
    storage_path: str
    status: str
    mime_type: str
    file_size: int
    confidence_score: Optional[float] = None
    doc_type_id: Optional[uuid.UUID] = None
    document_type: Optional[DocumentTypeOut] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    name: str
    status: str
    message: str

# Extracted Data
class ExtractedDataOut(BaseModel):
    document_id: uuid.UUID
    data: Dict[str, Any]
    confidence_scores: Optional[Dict[str, Any]] = None
    updated_at: datetime

    class Config:
        from_attributes = True

# Human Review
class DocumentReviewSubmit(BaseModel):
    action: str = Field(..., description="accepted, rejected, or edited")
    comments: Optional[str] = None
    data: Optional[Dict[str, Any]] = Field(None, description="Updated structured JSON data if action is 'edited'")

# Metrics
class TokenUsageDetail(BaseModel):
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    cost: float

class TokenUsageSummary(BaseModel):
    total_cost: float
    usage_by_model: List[TokenUsageDetail]

class WorkflowRunMetric(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    review_needed_runs: int
    average_latency_ms: float
