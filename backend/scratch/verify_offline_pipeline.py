import asyncio
import os
import fitz
from PIL import Image
import io
from app.agents.nodes import run_tesseract_ocr
from app.services.llm import llm_service

async def run_pipeline(file_path, filename):
    print(f"\n==========================================")
    print(f"RUNNING PIPELINE FOR: {filename}")
    
    # Read file bytes
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        
    # Run text extraction (selectable or OCR)
    extracted_text = ""
    if filename.lower().endswith(".pdf"):
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        is_certificate = "cert" in filename.lower() or "marks" in filename.lower() or "result" in filename.lower() or "sem" in filename.lower()
        for page in pdf_doc:
            text = page.get_text()
            page_text = text
            if (is_certificate and len(text.strip()) < 150) or not text.strip():
                # Run high quality OCR sweep
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = run_tesseract_ocr(img)
                if len(ocr_text.strip()) > len(text.strip()):
                    page_text = ocr_text
            pages_text.append(page_text)
        extracted_text = "\n".join(pages_text)
    else:
        img = Image.open(io.BytesIO(file_bytes))
        extracted_text = run_tesseract_ocr(img)
        
    print(f"Extracted Text Length: {len(extracted_text)}")
    
    # Run classification
    doc_type, _ = await llm_service.classify_document(extracted_text, filename)
    print(f"Classification: {doc_type}")
    
    # Run schema discovery
    schema_def, _ = await llm_service.discover_schema(extracted_text, doc_type)
    print(f"Schema Fields: {[f['name'] for f in schema_def['fields']]}")
    
    # Run extraction
    extracted_data, _ = await llm_service.extract_data(extracted_text, schema_def, doc_type, filename)
    print("Extracted Values:")
    for k, v in extracted_data.items():
        print(f"  {k}: {v}")
    
    return doc_type, extracted_data

async def main():
    llm_service.use_mock_openai = True
    llm_service.use_mock_anthropic = True
    
    base_dir = "/Users/leelanjan/AI_Document_Intelligence/AI-Document-Intelligence-Platform/backend/local_storage/raw/e6855f08-bac6-4eb3-9e36-b39b791681b8"
    
    # Test Aadhaar Card
    await run_pipeline(os.path.join(base_dir, "dc9e5074-b4ba-4c5e-95e5-40c4b1373ebb.pdf"), "ADDAR LEELANJAN.pdf")
    
    # Test PAN Card
    await run_pipeline(os.path.join(base_dir, "9a6dd4da-2792-43d5-a195-7309eb38d990.pdf"), "pan card leelanjan.pdf")
    
    # Test B.E ALL SEM RESULT
    await run_pipeline(os.path.join(base_dir, "d908f92d-b48b-4e82-8c1f-6b277761275b.pdf"), "B.E ALL SEM RESULT.pdf")
    
    # Test 10TH MARKS CARD
    await run_pipeline(os.path.join(base_dir, "483fc290-c41d-4fd8-9c25-4ff05ec2ab9d.pdf"), "10TH MARKS CARD LEELANJAN.pdf")

    # Test Identity Card (e-id-card)
    await run_pipeline(os.path.join(base_dir, "3d138832-f4bb-4e5e-92d0-9e439b72b816.pdf"), "e-id-card (1).pdf")

    # Test Certificate
    await run_pipeline(os.path.join(base_dir, "6e07801e-bc62-437c-aac7-e04976aefa3c.pdf"), "certificate-bthytfrkk3yp-1777437422 (1).pdf")

if __name__ == "__main__":
    asyncio.run(main())
