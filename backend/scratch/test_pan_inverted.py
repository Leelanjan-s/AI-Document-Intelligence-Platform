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
        stmt = select(Document).where(Document.name == "pan card leelanjan.pdf").order_by(Document.created_at.desc())
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
        
        # Resize 2x
        w, h = img.size
        img_resized = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(img_resized)
        
        pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
        
        # Sweep standard and inverted thresholds
        for thresh in [60, 80, 100, 110, 120, 130, 140, 150, 160, 170, 180]:
            # Standard
            binarized = gray.point(lambda p: 255 if p > thresh else 0)
            text_bin = pytesseract.image_to_string(binarized)
            print(f"--- STANDARD THRESH {thresh} (len={len(text_bin.strip())}) ---")
            if text_bin.strip():
                print(repr(text_bin))
                
            # Inverted
            binarized_inv = gray.point(lambda p: 0 if p > thresh else 255)
            text_bin_inv = pytesseract.image_to_string(binarized_inv)
            print(f"--- INVERTED THRESH {thresh} (len={len(text_bin_inv.strip())}) ---")
            if text_bin_inv.strip():
                print(repr(text_bin_inv))

if __name__ == "__main__":
    asyncio.run(main())
