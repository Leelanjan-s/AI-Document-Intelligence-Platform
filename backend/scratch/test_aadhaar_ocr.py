import asyncio
import os
import fitz
from PIL import Image, ImageOps
import io
import pytesseract

async def main():
    from app.db import database as db
    from app.models.models import Document
    from sqlalchemy import select
    from app.utils.s3 import storage
    
    storage.ensure_bucket_exists()
    async with db.async_session_maker() as session:
        stmt = select(Document).where(Document.name == "ADDAR LEELANJAN.pdf").order_by(Document.created_at.desc())
        res = await session.execute(stmt)
        doc = res.scalars().first()
        if not doc:
            print("Document not found")
            return
            
        file_bytes = await storage.download_file_bytes(doc.storage_path)
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = pdf_doc[0]
        
        pix = page.get_pixmap(dpi=300)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
        
        # 1. Standard OCR
        print("--- STANDARD OCR ---")
        print(repr(pytesseract.image_to_string(img)))
        
        # 2. Grayscale OCR
        gray = ImageOps.grayscale(img)
        print("--- GRAYSCALE OCR ---")
        print(repr(pytesseract.image_to_string(gray)))
        
        # 3. Sweep thresholds
        for thresh in [80, 100, 110, 120, 130, 140, 150, 160]:
            binarized = gray.point(lambda p: 255 if p > thresh else 0)
            text_bin = pytesseract.image_to_string(binarized)
            print(f"--- THRESHOLD {thresh} OCR (len={len(text_bin.strip())}) ---")
            if "4052" in text_bin or "LEELANJAN" in text_bin.upper():
                print(">>> SUCCESS AT THRESHOLD", thresh)
            print(repr(text_bin[:500]))
            
            # Inverted threshold
            binarized_inv = gray.point(lambda p: 0 if p > thresh else 255)
            text_bin_inv = pytesseract.image_to_string(binarized_inv)
            print(f"--- INVERTED THRESHOLD {thresh} OCR (len={len(text_bin_inv.strip())}) ---")
            if "4052" in text_bin_inv or "LEELANJAN" in text_bin_inv.upper():
                print(">>> SUCCESS INVERTED AT THRESHOLD", thresh)
            print(repr(text_bin_inv[:500]))

if __name__ == "__main__":
    asyncio.run(main())
