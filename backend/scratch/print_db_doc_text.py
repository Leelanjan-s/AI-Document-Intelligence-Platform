import asyncio
from sqlalchemy import select
from app.db import database as db
from app.models.models import Document
from app.utils.s3 import storage
import fitz
import io
from PIL import Image
from app.agents.nodes import run_tesseract_ocr

async def get_doc_text(name):
    async with db.async_session_maker() as session:
        doc_stmt = select(Document).where(Document.name == name).order_by(Document.created_at.desc())
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalars().first()
        if not doc:
            print(f"Document {name} not found")
            return None
            
        print(f"\n==========================================")
        print(f"Document: {doc.name} (ID: {doc.id})")
        print(f"Mime-Type: {doc.mime_type} | Storage Path: {doc.storage_path}")
        
        file_bytes = await storage.download_file_bytes(doc.storage_path)
        
        # Extracted text via PyMuPDF
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        print(f"Pages: {len(pdf_doc)}")
        
        for i, page in enumerate(pdf_doc):
            text = page.get_text()
            print(f"--- PAGE {i+1} SELECTABLE TEXT (len={len(text)}) ---")
            print(text[:1000])
            
            # If empty or we want to inspect OCR
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            ocr_text = run_tesseract_ocr(img)
            print(f"--- PAGE {i+1} OCR TEXT (len={len(ocr_text)}) ---")
            print(ocr_text[:1000])

async def main():
    storage.ensure_bucket_exists()
    await get_doc_text("ADDAR LEELANJAN.pdf")
    await get_doc_text("B.E ALL SEM RESULT.pdf")
    await get_doc_text("10TH MARKS CARD LEELANJAN.pdf")

if __name__ == "__main__":
    asyncio.run(main())
