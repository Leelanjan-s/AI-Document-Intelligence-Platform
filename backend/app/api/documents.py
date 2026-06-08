from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc, asc
from typing import List, Optional
import uuid
from datetime import datetime
from loguru import logger

from app.db.database import get_db
from app.models.models import Document, DocumentType, WorkflowRun, ExtractedData, Review, AuditLog, User
from app.schemas.schemas import DocumentOut, DocumentUploadResponse, ExtractedDataOut, DocumentReviewSubmit
from app.utils.s3 import storage
from app.workflows.orchestrator import orchestrator
from app.api.deps import get_current_user, RoleChecker

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a document to the object store and initiate processing agents asynchronously."""
    # Validate file size (e.g. limit to 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 10MB limit."
        )

    # Validate file type
    allowed_mimes = ["application/pdf", "image/png", "image/jpeg", "image/tiff"]
    if file.content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {file.content_type}. Allowed: PDF, PNG, JPG, TIFF"
        )

    # 1. Upload to MinIO
    doc_uuid = uuid.uuid4()
    extension = file.filename.split(".")[-1]
    storage_path = f"raw/{current_user.organization_id}/{doc_uuid}.{extension}"
    
    try:
        await storage.upload_file_bytes(storage_path, file_bytes, file.content_type)
    except Exception as e:
        logger.error(f"MinIO storage upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save file to S3 storage bucket"
        )

    # Convert string uuid to UUID object if present
    parsed_doc_type_id = None
    if doc_type_id:
        try:
            parsed_doc_type_id = uuid.UUID(doc_type_id)
        except ValueError:
            pass

    # 2. Record Document in Postgres
    doc = Document(
        id=doc_uuid,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        doc_type_id=parsed_doc_type_id,
        name=file.filename,
        storage_path=storage_path,
        status="uploaded",
        file_size=file_size,
        mime_type=file.content_type,
        created_at=datetime.utcnow()
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 3. Queue Background LangGraph Workflow Execution
    # We trigger the agent pipeline in the background using FastAPI BackgroundTasks
    background_tasks.add_task(
        orchestrator.run_document_workflow,
        doc_uuid,
        current_user.organization_id,
        current_user.id
    )

    # Audit the upload activity
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="document.upload",
        entity_type="document",
        entity_id=doc_uuid,
        action_metadata={"filename": file.filename}
    )
    db.add(audit)
    await db.commit()

    return DocumentUploadResponse(
        document_id=doc.id,
        name=doc.name,
        status=doc.status,
        message="Document uploaded successfully. Processing agents triggered."
    )

@router.get("", response_model=List[DocumentOut])
async def list_documents(
    limit: int = 10,
    offset: int = 0,
    status: Optional[str] = None,
    doc_type_id: Optional[uuid.UUID] = None,
    sort_by: str = "created_at",
    order: str = "desc",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve documents list with filtering, sorting, and pagination."""
    query = select(Document).where(Document.organization_id == current_user.organization_id)
    
    if status:
        query = query.where(Document.status == status)
    if doc_type_id:
        query = query.where(Document.doc_type_id == doc_type_id)
        
    # Apply sorting
    sort_column = getattr(Document, sort_by, Document.created_at)
    if order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
        
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    docs = result.scalars().all()
    
    # Load associated document types
    for doc in docs:
        if doc.doc_type_id:
            dt_stmt = select(DocumentType).where(DocumentType.id == doc.doc_type_id)
            dt_res = await db.execute(dt_stmt)
            doc.document_type = dt_res.scalar_one_or_none()
            
    return docs

@router.get("/{id}", response_model=DocumentOut)
async def get_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed metadata for a single document."""
    stmt = select(Document).where(
        Document.id == id,
        Document.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
        
    if doc.doc_type_id:
        dt_stmt = select(DocumentType).where(DocumentType.id == doc.doc_type_id)
        dt_res = await db.execute(dt_stmt)
        doc.document_type = dt_res.scalar_one_or_none()
        
    return doc

@router.get("/{id}/result", response_model=ExtractedDataOut)
async def get_document_result(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve structured data extraction and verification results."""
    # Ensure document exists and belongs to user organization
    doc_stmt = select(Document).where(
        Document.id == id,
        Document.organization_id == current_user.organization_id
    )
    doc_res = await db.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
        
    stmt = select(ExtractedData).where(ExtractedData.document_id == id)
    result = await db.execute(stmt)
    data = result.scalar_one_or_none()
    
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction results not yet available or document failed to process."
        )
        
    return data

@router.post("/{id}/review", status_code=status.HTTP_200_OK)
async def review_document(
    id: uuid.UUID,
    review_data: DocumentReviewSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(allowed_roles=["admin", "reviewer"]))
):
    """Submit a reviewer evaluation to accept, reject, or edit extracted values."""
    doc_stmt = select(Document).where(
        Document.id == id,
        Document.organization_id == current_user.organization_id
    )
    doc_res = await db.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get existing extracted data
    ext_stmt = select(ExtractedData).where(ExtractedData.document_id == id)
    ext_res = await db.execute(ext_stmt)
    ext = ext_res.scalar_one_or_none()
    
    previous_val = ext.data if ext else {}

    # Perform review updates based on action
    if review_data.action == "edited":
        if not review_data.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corrected data must be provided when action is 'edited'"
            )
        # Update JSON values
        if ext:
            ext.data = review_data.data
            ext.updated_at = datetime.utcnow()
        doc.status = "completed"
        # Reset confidence to 1.0 (fully human verified)
        doc.confidence_score = 1.0
        
    elif review_data.action == "accepted":
        doc.status = "completed"
        doc.confidence_score = 1.0
        
    elif review_data.action == "rejected":
        doc.status = "failed"
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid review action. Allowed: accepted, rejected, edited"
        )

    # Save Review audit log in database
    review = Review(
        id=uuid.uuid4(),
        document_id=id,
        reviewer_id=current_user.id,
        previous_data=previous_val,
        updated_data=review_data.data if review_data.action == "edited" else previous_val,
        action=review_data.action,
        comments=review_data.comments,
        created_at=datetime.utcnow()
    )
    db.add(review)

    # Add audit log
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action=f"document.review.{review_data.action}",
        entity_type="document",
        entity_id=id,
        action_metadata={"reviewer_email": current_user.email}
    )
    db.add(audit)
    
    await db.commit()
    return {"message": f"Document review submitted successfully. Status updated to {doc.status}."}

@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document and its associated records from storage and database."""
    stmt = select(Document).where(
        Document.id == id,
        Document.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
        
    # Delete from S3 storage if possible
    try:
        await storage.delete_file(doc.storage_path)
    except Exception as e:
        logger.warning(f"Failed to delete S3 file {doc.storage_path}: {e}")
        
    # Delete database record (cascading takes care of workflow runs, extracted data, reviews)
    await db.delete(doc)
    
    # Audit log
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="document.delete",
        entity_type="document",
        entity_id=id,
        action_metadata={"filename": doc.name}
    )
    db.add(audit)
    await db.commit()
    
    return {"message": "Document deleted successfully"}

@router.get("/{id}/file")
async def get_document_file(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the original document file bytes for rendering."""
    stmt = select(Document).where(Document.id == id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
        
    try:
        file_bytes = await storage.download_file_bytes(doc.storage_path)
        from fastapi import Response
        return Response(content=file_bytes, media_type=doc.mime_type)
    except Exception as e:
        logger.error(f"Failed to fetch file from storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve file from storage"
        )

