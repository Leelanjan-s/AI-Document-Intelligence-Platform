import asyncio
import io
import fitz
from PIL import Image
from app.db import database as db
from app.models.models import Document
from app.utils.s3 import storage
from app.agents.nodes import run_tesseract_ocr

async def main():
    async with db.async_session_maker() as session:
        from sqlalchemy import select
        stmt = select(Document).where(Document.name.like("%12TH MARKS CARD%"))
        res = await session.execute(stmt)
        doc = res.scalars().first()
        
        if not doc:
            print("12th Marks Card document not found in DB.")
            return
            
        print(f"Found doc: {doc.name} (ID: {doc.id}, Storage Path: {doc.storage_path})")
        
        storage.ensure_bucket_exists()
        file_bytes = await storage.download_file_bytes(doc.storage_path)
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        print("Page count:", len(pdf_doc))
        
        for i, page in enumerate(pdf_doc):
            text = page.get_text()
            print(f"\n--- PAGE {i} SELECTABLE TEXT ---")
            print(repr(text))
            
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = run_tesseract_ocr(img)
            print(f"\n--- PAGE {i} OCR TEXT ---")
            print(ocr_text[:3000])

if __name__ == "__main__":
    asyncio.run(main())
