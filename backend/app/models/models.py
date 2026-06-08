import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Float, Integer, JSON, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="organization")
    document_types: Mapped[List["DocumentType"]] = relationship(back_populates="organization")
    documents: Mapped[List["Document"]] = relationship(back_populates="organization")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="organization")
    token_usage: Mapped[List["TokenUsage"]] = relationship(back_populates="organization")

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")  # admin, reviewer, user
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship(back_populates="users")
    documents: Mapped[List["Document"]] = relationship(back_populates="user")
    reviews: Mapped[List["Review"]] = relationship(back_populates="reviewer")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
    token_usage: Mapped[List["TokenUsage"]] = relationship(back_populates="user")

class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    schema_definition: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False) # e.g. {"fields": [{"name": "invoice_num", "type": "str", "required": true}]}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship(back_populates="document_types")
    documents: Mapped[List["Document"]] = relationship(back_populates="document_type")

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    doc_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("document_types.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)  # raw/invoice_abc.pdf
    status: Mapped[str] = mapped_column(String(50), default="uploaded")  # uploaded, processing, review_needed, completed, failed
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship(back_populates="documents")
    user: Mapped[Optional[User]] = relationship(back_populates="documents")
    document_type: Mapped[Optional[DocumentType]] = relationship(back_populates="documents")
    workflow_runs: Mapped[List["WorkflowRun"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    extracted_data: Mapped[Optional["ExtractedData"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    reviews: Mapped[List["Review"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    token_usage: Mapped[List["TokenUsage"]] = relationship(back_populates="document")

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running")  # running, completed, failed, review_needed
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    document: Mapped[Document] = relationship(back_populates="workflow_runs")
    agent_executions: Mapped[List["AgentExecution"]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")

class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)  # ocr_agent, classification_agent, etc.
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # success, failed
    input_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.001}
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="agent_executions")

class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence_scores: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # {"invoice_number": 0.95, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document: Mapped[Document] = relationship(back_populates="extracted_data")

class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    previous_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    updated_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # accepted, rejected, edited
    comments: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document: Mapped[Document] = relationship(back_populates="reviews")
    reviewer: Mapped[User] = relationship(back_populates="reviews")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)  # user.login, document.upload, document.review
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # user, document, review
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    action_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship(back_populates="audit_logs")
    user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")

class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(String(2000), nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship(back_populates="token_usage")
    user: Mapped[Optional[User]] = relationship(back_populates="token_usage")
    document: Mapped[Optional[Document]] = relationship(back_populates="token_usage")
