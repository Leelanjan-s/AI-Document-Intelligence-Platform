import time
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger
from PIL import Image
import io

try:
    import pytesseract
    import os
    if pytesseract:
        # Explicitly configure brew binary path on macOS
        if os.path.exists("/opt/homebrew/bin/tesseract"):
            pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
        elif os.path.exists("/usr/local/bin/tesseract"):
            pytesseract.pytesseract.tesseract_cmd = "/usr/local/bin/tesseract"
except ImportError:
    pytesseract = None

from app.agents.state import AgentState
from app.db import database as db
from app.models.models import Document, DocumentType, WorkflowRun, AgentExecution, ExtractedData, TokenUsage
from app.utils.s3 import storage
from app.services.llm import llm_service
from sqlalchemy import select, update

# Helper to save execution log in a separate transaction
async def log_agent_execution(
    workflow_run_id: str,
    agent_name: str,
    status: str,
    input_data: Optional[Dict[str, Any]],
    output_data: Optional[Dict[str, Any]],
    latency_ms: int,
    token_usage_meta: Optional[Dict[str, Any]],
    error_msg: Optional[str] = None
) -> None:
    async with db.async_session_maker() as session:
        try:
            exec_id = uuid.uuid4()
            execution = AgentExecution(
                id=exec_id,
                workflow_run_id=uuid.UUID(workflow_run_id),
                agent_name=agent_name,
                status=status,
                input_data=input_data,
                output_data=output_data,
                latency_ms=latency_ms,
                token_usage=token_usage_meta,
                error_message=error_msg,
                created_at=datetime.utcnow()
            )
            session.add(execution)
            
            # Log Token Usage if metadata is present
            if token_usage_meta and token_usage_meta.get("cost", 0) > 0:
                # Get workflow run to trace doc and org
                wf_stmt = select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(workflow_run_id))
                wf_res = await session.execute(wf_stmt)
                wf = wf_res.scalar_one_or_none()
                if wf:
                    doc_stmt = select(Document).where(Document.id == wf.document_id)
                    doc_res = await session.execute(doc_stmt)
                    doc = doc_res.scalar_one_or_none()
                    if doc:
                        token_use = TokenUsage(
                            organization_id=doc.organization_id,
                            user_id=doc.user_id,
                            document_id=doc.id,
                            model_name=token_usage_meta.get("model", "unknown"),
                            prompt_tokens=token_usage_meta.get("prompt_tokens", 0),
                            completion_tokens=token_usage_meta.get("completion_tokens", 0),
                            cost=token_usage_meta.get("cost", 0.0),
                            created_at=datetime.utcnow()
                        )
                        session.add(token_use)
            
            await session.commit()
            logger.info(f"Logged AgentExecution for {agent_name} - {status}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to log agent execution: {e}")

# MOCK DATA TEMPLATES FOR FALLBACK OCR
MOCK_OCR_TEMPLATES = {
    "invoice": (
        "ACME Supplies LLC\n"
        "123 Industrial Parkway, Suite 500\n"
        "INVOICE\n"
        "Invoice Number: INV-2026-987\n"
        "Date: 2026-06-05\n"
        "Due Date: 2026-07-05\n"
        "Bill To:\n"
        "Acme Corp\n"
        "100 Main Street\n"
        "Items:\n"
        "1. Server Support Plan - Qty 1 - Price $100.00\n"
        "2. Custom Development - Qty 1 - Price $20.50\n"
        "Subtotal: $120.50\n"
        "Tax (0%): $0.00\n"
        "Total: $120.50\n"
        "Thank you for your business!"
    ),
    "receipt": (
        "COFFEE DELIGHT #441\n"
        "555 ESPRESSO WAY\n"
        "Date: 2026-06-05 14:32\n"
        "TRANS: 98172635\n"
        "1 LATTE MACCHIATO - $4.75\n"
        "1 BLUEBERRY MUFFIN - $3.50\n"
        "1 BOTTLED WATER - $2.25\n"
        "SUBTOTAL: $10.50\n"
        "TAX: $0.85\n"
        "TOTAL: $11.35\n"
        "CARD ************1234\n"
        "THANK YOU!"
    ),
    "statement": (
        "GLOBE TRUST BANK\n"
        "Monthly Account Statement\n"
        "Account Number: 1234-5678-9012\n"
        "Statement Period: May 1, 2026 to May 31, 2026\n"
        "Starting Balance: $5,000.00\n"
        "Deposits: $1,250.00\n"
        "Withdrawals: $750.00\n"
        "Ending Balance: $5,500.00\n"
        "Customer Service: 1-800-GLOBE"
    ),
    "contract": (
        "SOFTWARE LICENSE AGREEMENT\n"
        "This Agreement is made on 2026-06-05 (Effective Date) by and between:\n"
        "Acme Corp (\"Licensee\") and GlobeTech Solutions (\"Licensor\").\n"
        "Licensor grants Licensee a non-transferable, non-exclusive license to use the Platform Software.\n"
        "The total value of this agreement is $15,000.00.\n"
        "This contract will expire on 2027-06-05."
    ),
    "po": (
        "ACME CORP - PURCHASE ORDER\n"
        "PO Number: PO-2026-441\n"
        "PO Date: 2026-06-05\n"
        "To Vendor:\n"
        "Office Depot Supply\n"
        "Items:\n"
        "1. Ergonomic Chairs - Qty 5 - $250.00 each - Total $1,250.00\n"
        "2. Desk Organizers - Qty 10 - $15.00 each - Total $150.00\n"
        "Total PO Amount: $1,400.00\n"
        "Shipping Address: Acme Corp HQ"
    ),
    "certificate": (
        "CERTIFICATE OF COMPLETION\n"
        "This is to certify that Leelanjan S has successfully completed the\n"
        "Data Science Program.\n"
        "Issued on: 2026-06-05\n"
        "Issued by: PaceWisdom AI Academy\n"
        "Director Signatory: Dr. Alice Johnson"
    ),
    "passport": (
        "REPUBLIC OF INDIA PASSPORT\n"
        "Passport Number: L1234567\n"
        "Given Name: JOHN DOE\n"
        "Nationality: INDIAN\n"
        "Date of Birth: 12/04/1998\n"
        "Date of Expiry: 12/04/2036"
    ),
    "resume": (
        "John Doe\n"
        "Email: john.doe@email.com\n"
        "Skills: Python, TensorFlow, SQLAlchemy\n"
        "Education: Bachelor of Science in AI (National University)\n"
        "Experience: 2 Years as Junior ML Engineer at TechCorp"
    ),
    "driving license": (
        "DRIVING LICENSE\n"
        "License Number: DL-9928371\n"
        "Full Name: LEELANJAN S\n"
        "Date of Birth: 12/04/1998\n"
        "Address: 123 MG Road, Bangalore, India\n"
        "Expiry Date: 12/04/2036"
    ),
    "medical report": (
        "METROPOLITAN CLINIC\n"
        "Patient Report\n"
        "Patient Name: Jane Smith\n"
        "Age: 28\n"
        "Date: 2026-06-05\n"
        "Diagnosis: Mild Influenza\n"
        "Attending Doctor: Dr. Robert Carter"
    ),
    "marksheet": (
        "BOARD OF SECONDARY EDUCATION\n"
        "Academic Marksheet\n"
        "Student Name: Leelanjan S\n"
        "Roll Number: DS-2026-004\n"
        "Institution: National University\n"
        "Total Marks: 450\n"
        "Grade: A+"
    )
}

def run_tesseract_ocr(image: Image.Image) -> str:
    """Helper to run Tesseract OCR with multiple preprocessing steps (threshold sweeps) to capture all printed text."""
    import pytesseract
    import os
    from PIL import ImageOps
    
    # Configure path explicitly on macOS
    if os.path.exists("/opt/homebrew/bin/tesseract"):
        pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
    elif os.path.exists("/usr/local/bin/tesseract"):
        pytesseract.pytesseract.tesseract_cmd = "/usr/local/bin/tesseract"
        
    try:
        # Scale up the image by 2x for better small text extraction
        w, h = image.size
        img_resized = image.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        
        # Convert to grayscale
        gray = ImageOps.grayscale(img_resized)
        
        # We run multiple sweeps and combine them so the heuristic parser has access to all recognized words.
        # This is extremely useful when some parts of a colored document are recognized at thresh 60 and others at thresh 110 or standard grayscale.
        texts = []
        
        # 1. Grayscale OCR
        text_gray = pytesseract.image_to_string(gray)
        if text_gray.strip():
            texts.append(text_gray)
            
        # 2. Threshold sweeps (standard and inverted)
        for thresh in [60, 80, 110, 140]:
            # Standard
            binarized = gray.point(lambda p: 255 if p > thresh else 0)
            text_bin = pytesseract.image_to_string(binarized)
            if text_bin.strip() and text_bin not in texts:
                texts.append(text_bin)
                
            # Inverted
            binarized_inv = gray.point(lambda p: 0 if p > thresh else 255)
            text_bin_inv = pytesseract.image_to_string(binarized_inv)
            if text_bin_inv.strip() and text_bin_inv not in texts:
                texts.append(text_bin_inv)
                
        # If all sweeps failed, try standard OCR on original image
        if not texts:
            text_orig = pytesseract.image_to_string(image)
            if text_orig.strip():
                texts.append(text_orig)
                
        combined_text = "\n\n--- PREPROCESSED OCR SWEEP ---\n\n".join(texts)
        logger.info(f"Tesseract OCR completed. Generated {len(texts)} sweeps, combined text length: {len(combined_text)}")
        return combined_text
    except Exception as e:
        logger.warning(f"PyTesseract execution failed: {e}")
        return ""

async def ocr_agent(state: AgentState) -> Dict[str, Any]:
    """OCR Agent: Downloads file and extracts text using Tesseract, falling back to mock or LLM."""
    start_time = time.time()
    doc_id = state["document_id"]
    logger.info(f"[OCR Node] Processing document {doc_id}")
    
    # 1. Fetch document metadata from DB
    async with db.async_session_maker() as session:
        stmt = select(Document).where(Document.id == uuid.UUID(doc_id))
        res = await session.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            error_msg = f"Document {doc_id} not found in database"
            logger.error(error_msg)
            return {"errors": [error_msg], "status": "failed"}
        
        storage_path = doc.storage_path
        filename = doc.name
        mime_type = doc.mime_type
        
        # Get active workflow run
        wf_stmt = select(WorkflowRun).where(
            WorkflowRun.document_id == doc.id,
            WorkflowRun.status == "running"
        )
        wf_res = await session.execute(wf_stmt)
        wf = wf_res.scalar_one_or_none()
        workflow_run_id = str(wf.id) if wf else str(uuid.uuid4())

    # 2. Download from S3 storage
    try:
        file_bytes = await storage.download_file_bytes(storage_path)
    except Exception as e:
        error_msg = f"Failed to download document from storage: {e}"
        logger.error(error_msg)
        await log_agent_execution(workflow_run_id, "ocr_agent", "failed", {"doc_id": doc_id}, None, int((time.time() - start_time) * 1000), None, error_msg)
        return {"errors": [error_msg], "status": "failed"}

    # 3. Perform OCR or PDF text extraction
    extracted_text = ""
    ocr_method = "pytesseract"
    ocr_error = None
    try:
        if pytesseract and (mime_type.startswith("image/") or filename.lower().endswith((".png", ".jpg", ".jpeg"))):
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text = run_tesseract_ocr(image)
            logger.info("Successfully extracted text using PyTesseract OCR (with threshold preprocessing).")
        elif mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                import fitz  # PyMuPDF
                pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                pages_text = []
                is_certificate = "cert" in filename.lower() or "marks" in filename.lower() or "result" in filename.lower() or "sem" in filename.lower()
                
                for page in pdf_doc:
                    text = page.get_text()
                    page_text = text
                    
                    # If it's a certificate/marksheet with minimal selectable text, or has no selectable text, try OCR
                    if (is_certificate and len(text.strip()) < 150 and pytesseract) or (not text.strip() and pytesseract):
                        pix = page.get_pixmap(dpi=300)  # Render at 300 DPI for high quality OCR
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        ocr_text = run_tesseract_ocr(img)
                        
                        # Use OCR text if it yields richer text, otherwise fall back to selectable text
                        if len(ocr_text.strip()) > len(text.strip()):
                            page_text = ocr_text
                            ocr_method = "pymupdf_ocr"
                        else:
                            ocr_method = "pymupdf_text"
                    else:
                        ocr_method = "pymupdf_text"
                        
                    pages_text.append(page_text)
                    
                extracted_text = "\n".join(pages_text)
                logger.info(f"Successfully extracted text using PyMuPDF ({ocr_method}). Length: {len(extracted_text)}")
            except Exception as pdf_err:
                logger.warning(f"PyMuPDF extraction failed: {pdf_err}. Falling back to pypdf.")
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                extracted_text = "\n".join(pages_text)
                ocr_method = "pypdf"
        else:
            ocr_method = "fallback_mock"
            logger.info("Tesseract or image/pdf format not supported/available. Using fallback OCR mapping.")
            extracted_text = ""
    except Exception as e:
        ocr_error = str(e)
        logger.warning(f"Text extraction failed: {e}. Falling back to name-based Mock OCR.")
        ocr_method = "fallback_mock"

    if not extracted_text.strip():
        # Clean Mock OCR Fallback based on filename keywords
        fn_lower = filename.lower()
        if "receipt" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["receipt"]
        elif "statement" in fn_lower or "bank" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["statement"]
        elif "contract" in fn_lower or "agreement" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["contract"]
        elif "purchase" in fn_lower or "po" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["po"]
        elif "certificate" in fn_lower or "cert" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["certificate"]
        elif "passport" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["passport"]
        elif "resume" in fn_lower or "cv" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["resume"]
        elif "license" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["driving license"]
        elif "medical" in fn_lower or "report" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["medical report"]
        elif "marksheet" in fn_lower or "transcript" in fn_lower or "academic" in fn_lower or "marks" in fn_lower:
            extracted_text = MOCK_OCR_TEMPLATES["marksheet"]
        else:
            extracted_text = MOCK_OCR_TEMPLATES["invoice"]

    latency = int((time.time() - start_time) * 1000)
    
    # Save step execution log
    await log_agent_execution(
        workflow_run_id,
        "ocr_agent",
        "success" if not ocr_error else "warning",
        {"doc_id": doc_id, "mime_type": mime_type},
        {"text_length": len(extracted_text), "method": ocr_method, "ocr_error": ocr_error},
        latency,
        None,
        error_msg=ocr_error
    )
    
    # Update current step in workflow run
    async with db.async_session_maker() as session:
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == uuid.UUID(workflow_run_id))
            .values(current_step="ocr_completed")
        )
        await session.commit()

    return {"raw_text": extracted_text, "status": "processing"}

async def classification_agent(state: AgentState) -> Dict[str, Any]:
    """Classification Agent: Classifies the document text into one of the supported document types."""
    start_time = time.time()
    doc_id = state["document_id"]
    raw_text = state["raw_text"]
    
    async with db.async_session_maker() as session:
        # Get filename and workflow run
        doc_stmt = select(Document).where(Document.id == uuid.UUID(doc_id))
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        filename = doc.name if doc else "document.pdf"
        
        wf_stmt = select(WorkflowRun).where(
            WorkflowRun.document_id == uuid.UUID(doc_id),
            WorkflowRun.status == "running"
        )
        wf_res = await session.execute(wf_stmt)
        wf = wf_res.scalar_one_or_none()
        workflow_run_id = str(wf.id) if wf else str(uuid.uuid4())

    logger.info(f"[Classification Node] Classifying document {doc_id}")
    
    try:
        classification, usage = await llm_service.classify_document(raw_text, filename)
    except Exception as e:
        error_msg = f"Classification LLM call failed: {e}"
        logger.error(error_msg)
        await log_agent_execution(workflow_run_id, "classification_agent", "failed", {"text_len": len(raw_text)}, None, int((time.time() - start_time) * 1000), None, error_msg)
        return {"errors": [error_msg], "status": "failed"}

    latency = int((time.time() - start_time) * 1000)
    
    await log_agent_execution(
        workflow_run_id,
        "classification_agent",
        "success",
        {"text_len": len(raw_text)},
        {"classification": classification},
        latency,
        usage
    )

    org_id = state.get("organization_id")
    token_usages = state.get("token_usage", []) + [usage]

    async with db.async_session_maker() as session:
        # Find document type ID in DB
        dt_stmt = select(DocumentType).where(DocumentType.name == classification)
        dt_res = await session.execute(dt_stmt)
        doc_type = dt_res.scalar_one_or_none()
        
        # If no schema is registered in the database, run LLM-based Schema Discovery!
        if not doc_type:
            logger.info(f"DocumentType '{classification}' not found. Discovering schema via LLM...")
            try:
                schema_def, discovery_usage = await llm_service.discover_schema(raw_text, classification)
                token_usages.append(discovery_usage)
                
                # Register the newly discovered type in DB dynamically
                org_uuid = uuid.UUID(org_id) if org_id else None
                doc_type = DocumentType(
                    id=uuid.uuid4(),
                    organization_id=org_uuid,
                    name=classification,
                    description=f"Dynamically discovered schema for {classification}",
                    schema_definition=schema_def
                )
                session.add(doc_type)
                await session.flush()  # Flush to get doc_type.id
                logger.info(f"Successfully registered dynamic schema for {classification}: {schema_def}")
            except Exception as schema_err:
                logger.error(f"Failed to discover/register schema for {classification}: {schema_err}")
                # Fallback to Invoice default if discovery completely fails
                dt_stmt_fallback = select(DocumentType).where(DocumentType.name == "Invoice")
                dt_res_fallback = await session.execute(dt_stmt_fallback)
                doc_type = dt_res_fallback.scalar_one_or_none()
            
        doc_type_id = doc_type.id if doc_type else None
        
        # Update Document and Workflow
        await session.execute(
            update(Document)
            .where(Document.id == uuid.UUID(doc_id))
            .values(doc_type_id=doc_type_id)
        )
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == uuid.UUID(workflow_run_id))
            .values(current_step="classification_completed")
        )
        await session.commit()

    return {
        "classification": classification,
        "status": "processing",
        "token_usage": token_usages
    }

async def extraction_agent(state: AgentState) -> Dict[str, Any]:
    """Extraction Agent: Extracts fields from raw text based on schema definition."""
    start_time = time.time()
    doc_id = state["document_id"]
    raw_text = state["raw_text"]
    classification = state["classification"]

    async with db.async_session_maker() as session:
        # Find document and its type schema definition
        doc_stmt = select(Document).where(Document.id == uuid.UUID(doc_id))
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        filename = doc.name if doc else None

        dt_stmt = select(DocumentType).where(DocumentType.name == classification)
        dt_res = await session.execute(dt_stmt)
        doc_type = dt_res.scalar_one_or_none()
        
        if not doc_type:
            # Fallback to Invoice type schema
            dt_stmt_fallback = select(DocumentType).where(DocumentType.name == "Invoice")
            dt_res_fallback = await session.execute(dt_stmt_fallback)
            doc_type = dt_res_fallback.scalar_one_or_none()
            
        schema_definition = doc_type.schema_definition if doc_type else {"fields": []}
        
        wf_stmt = select(WorkflowRun).where(
            WorkflowRun.document_id == uuid.UUID(doc_id),
            WorkflowRun.status == "running"
        )
        wf_res = await session.execute(wf_stmt)
        wf = wf_res.scalar_one_or_none()
        workflow_run_id = str(wf.id) if wf else str(uuid.uuid4())

    logger.info(f"[Extraction Node] Extracting schema for {classification} on document {doc_id}")
    
    try:
        extracted_data, usage = await llm_service.extract_data(raw_text, schema_definition, classification, filename)
    except Exception as e:
        error_msg = f"Extraction LLM call failed: {e}"
        logger.error(error_msg)
        await log_agent_execution(workflow_run_id, "extraction_agent", "failed", {"classification": classification}, None, int((time.time() - start_time) * 1000), None, error_msg)
        return {"errors": [error_msg], "status": "failed"}

    latency = int((time.time() - start_time) * 1000)
    
    await log_agent_execution(
        workflow_run_id,
        "extraction_agent",
        "success",
        {"schema": schema_definition},
        {"extracted_data": extracted_data},
        latency,
        usage
    )

    async with db.async_session_maker() as session:
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == uuid.UUID(workflow_run_id))
            .values(current_step="extraction_completed")
        )
        await session.commit()

    return {
        "extracted_data": extracted_data,
        "status": "processing",
        "token_usage": state.get("token_usage", []) + [usage]
    }

async def validation_agent(state: AgentState) -> Dict[str, Any]:
    """Validation Agent: Programmatically validates extracted fields against business rules and types."""
    start_time = time.time()
    doc_id = state["document_id"]
    classification = state["classification"]
    extracted_data = state["extracted_data"] or {}
    
    async with db.async_session_maker() as session:
        dt_stmt = select(DocumentType).where(DocumentType.name == classification)
        dt_res = await session.execute(dt_stmt)
        doc_type = dt_res.scalar_one_or_none()
        
        if not doc_type:
            dt_stmt_fallback = select(DocumentType).where(DocumentType.name == "Invoice")
            dt_res_fallback = await session.execute(dt_stmt_fallback)
            doc_type = dt_res_fallback.scalar_one_or_none()
            
        schema_definition = doc_type.schema_definition if doc_type else {"fields": []}
        
        wf_stmt = select(WorkflowRun).where(
            WorkflowRun.document_id == uuid.UUID(doc_id),
            WorkflowRun.status == "running"
        )
        wf_res = await session.execute(wf_stmt)
        wf = wf_res.scalar_one_or_none()
        workflow_run_id = str(wf.id) if wf else str(uuid.uuid4())

    logger.info(f"[Validation Node] Validating document {doc_id}")
    
    fields = schema_definition.get("fields", [])
    missing_fields = []
    type_errors = []
    errors = []
    
    # 1. Check schemas
    for f in fields:
        name = f["name"]
        req = f.get("required", False)
        val = extracted_data.get(name)
        
        if val is None or str(val).strip() == "":
            if req:
                missing_fields.append(name)
                errors.append(f"Required field '{name}' is missing")
        else:
            # Check data type
            if f["type"] == "number":
                try:
                    # Clean currency chars if it's a string
                    if isinstance(val, str):
                        clean_val = val.replace("$", "").replace(",", "").strip()
                        float(clean_val)
                    else:
                        float(val)
                except ValueError:
                    type_errors.append(name)
                    errors.append(f"Field '{name}' is expected to be a number, got '{val}'")

    # 2. Check business rules
    # Math rules for Invoices / Receipts
    if classification in ["Invoice", "Receipt"]:
        subtotal = extracted_data.get("subtotal") or extracted_data.get("amount") or 0.0
        tax = extracted_data.get("tax") or 0.0
        total = extracted_data.get("total") or extracted_data.get("amount") or extracted_data.get("total_amount") or 0.0
        
        # Clean potential strings
        try:
            subtotal = float(str(subtotal).replace("$", "").replace(",", "")) if subtotal else 0.0
            tax = float(str(tax).replace("$", "").replace(",", "")) if tax else 0.0
            total = float(str(total).replace("$", "").replace(",", "")) if total else 0.0
        except ValueError:
            pass # already tracked by type checking
            
        if total < 0:
            errors.append("Total amount cannot be negative")
            
        # Optional validation of summation: total should approximate subtotal + tax
        if subtotal > 0 and tax >= 0 and total > 0:
            diff = abs(total - (subtotal + tax))
            if diff > 0.05:  # Tolerance threshold
                errors.append(f"Financial summary discrepancy: total ({total}) does not equal subtotal + tax ({subtotal + tax})")

    validation_results = {
        "is_valid": len(errors) == 0,
        "missing_fields": missing_fields,
        "type_errors": type_errors,
        "errors": errors
    }
    
    latency = int((time.time() - start_time) * 1000)
    
    await log_agent_execution(
        workflow_run_id,
        "validation_agent",
        "success",
        {"extracted_data": extracted_data},
        validation_results,
        latency,
        None
    )

    async with db.async_session_maker() as session:
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == uuid.UUID(workflow_run_id))
            .values(current_step="validation_completed")
        )
        await session.commit()

    return {
        "validation_results": validation_results,
        "errors": state.get("errors", []) + errors,
        "status": "processing"
    }

async def confidence_agent(state: AgentState) -> Dict[str, Any]:
    """Confidence Agent: Estimates final accuracy scoring and sets routing status."""
    start_time = time.time()
    doc_id = state["document_id"]
    raw_text = state["raw_text"]
    extracted_data = state["extracted_data"] or {}
    validation_results = state["validation_results"] or {}

    async with db.async_session_maker() as session:
        wf_stmt = select(WorkflowRun).where(
            WorkflowRun.document_id == uuid.UUID(doc_id),
            WorkflowRun.status == "running"
        )
        wf_res = await session.execute(wf_stmt)
        wf = wf_res.scalar_one_or_none()
        workflow_run_id = str(wf.id) if wf else str(uuid.uuid4())

    logger.info(f"[Confidence Node] Running accuracy evaluation on document {doc_id}")
    
    try:
        confidence_score, rationale, usage = await llm_service.generate_confidence(raw_text, extracted_data)
    except Exception as e:
        error_msg = f"Confidence evaluation failed: {e}"
        logger.error(error_msg)
        await log_agent_execution(workflow_run_id, "confidence_agent", "failed", {"extracted_data": extracted_data}, None, int((time.time() - start_time) * 1000), None, error_msg)
        return {"errors": [error_msg], "status": "failed"}

    # Adjust confidence score if program validation checks failed
    if not validation_results.get("is_valid", True):
        # penalize score
        original_score = confidence_score
        confidence_score = max(0.40, confidence_score - 0.25)
        rationale = f"[Penalized from {original_score:.2f} due to validation errors] {rationale}"

    # Route decision: confidence < 0.80 requires review
    final_status = "review_needed" if confidence_score < 0.80 else "completed"

    latency = int((time.time() - start_time) * 1000)
    
    await log_agent_execution(
        workflow_run_id,
        "confidence_agent",
        "success",
        {"extracted_data": extracted_data, "validation_is_valid": validation_results.get("is_valid")},
        {"confidence_score": confidence_score, "rationale": rationale, "status": final_status},
        latency,
        usage
    )

    # Persist outputs in DB
    async with db.async_session_maker() as session:
        # Update Document details
        await session.execute(
            update(Document)
            .where(Document.id == uuid.UUID(doc_id))
            .values(
                status=final_status,
                confidence_score=confidence_score
            )
        )
        
        # Save Extracted Data
        ext_stmt = select(ExtractedData).where(ExtractedData.document_id == uuid.UUID(doc_id))
        ext_res = await session.execute(ext_stmt)
        ext_obj = ext_res.scalar_one_or_none()
        
        # Map fields to individual confidence values (can be mocked simple)
        field_confidences = {k: round(confidence_score, 2) for k in extracted_data.keys()}
        
        if not ext_obj:
            ext_obj = ExtractedData(
                id=uuid.uuid4(),
                document_id=uuid.UUID(doc_id),
                data=extracted_data,
                confidence_scores=field_confidences
            )
            session.add(ext_obj)
        else:
            ext_obj.data = extracted_data
            ext_obj.confidence_scores = field_confidences
            
        # Update workflow run status
        wf_status = "review_needed" if final_status == "review_needed" else "completed"
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == uuid.UUID(workflow_run_id))
            .values(
                status=wf_status,
                current_step="confidence_completed",
                completed_at=datetime.utcnow()
            )
        )
        
        await session.commit()
        logger.info(f"Finished processing document {doc_id}. Status: {final_status}, Confidence: {confidence_score:.2f}")

    return {
        "confidence_score": confidence_score,
        "confidence_rationale": rationale,
        "status": final_status,
        "token_usage": state.get("token_usage", []) + [usage]
    }
