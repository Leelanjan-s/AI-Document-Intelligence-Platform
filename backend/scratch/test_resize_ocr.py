import asyncio
import os
import fitz
from PIL import Image, ImageOps
import io
import pytesseract

async def test_resize_ocr(doc_name):
    from app.db import database as db
    from app.models.models import Document
    from sqlalchemy import select
    from app.utils.s3 import storage
    
    async with db.async_session_maker() as session:
        stmt = select(Document).where(Document.name == doc_name).order_by(Document.created_at.desc())
        res = await session.execute(stmt)
        doc = res.scalars().first()
        if not doc:
            print(f"Document {doc_name} not found")
            return
            
        file_bytes = await storage.download_file_bytes(doc.storage_path)
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = pdf_doc[0]
        
        pix = page.get_pixmap(dpi=300)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Resize image: Scale up by 2x
        w, h = img.size
        img_resized = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        
        pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
        
        print(f"\n==========================================")
        print(f"Document: {doc_name} (Resized 2x)")
        
        # Grayscale
        gray = ImageOps.grayscale(img_resized)
        
        # Standard Grayscale OCR
        text_gray = pytesseract.image_to_string(gray)
        print("--- GRAYSCALE OCR ---")
        print(repr(text_gray))
        
        # Binarization sweeps
        for thresh in [100, 120, 140, 150]:
            binarized = gray.point(lambda p: 255 if p > thresh else 0)
            text_bin = pytesseract.image_to_string(binarized)
            print(f"--- THRESHOLD {thresh} OCR (len={len(text_bin.strip())}) ---")
            print(repr(text_bin[:600]))

async def main():
    from app.utils.s3 import storage
    storage.ensure_bucket_exists()
    await test_resize_ocr("ADDAR LEELANJAN.pdf")
    await test_resize_ocr("pan card leelanjan.pdf")

if __name__ == "__main__":
    asyncio.run(main())
