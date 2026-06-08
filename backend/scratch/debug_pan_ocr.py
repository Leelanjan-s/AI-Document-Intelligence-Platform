import asyncio
import os
import fitz
from PIL import Image, ImageOps
import io
import pytesseract
import cv2
import numpy as np

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
        
        # Convert to OpenCV image
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
        
        # Try a few advanced preprocessing methods
        # 1. Otsu's thresholding
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text_otsu = pytesseract.image_to_string(otsu)
        print("--- OTSU OCR ---")
        print(repr(text_otsu))
        
        # 2. Adaptive thresholding
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        text_adaptive = pytesseract.image_to_string(adaptive)
        print("--- ADAPTIVE GAUSSIAN OCR ---")
        print(repr(text_adaptive))
        
        # 3. Resizing + Otsu
        img_resized = cv2.resize(gray, (0,0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, otsu_resized = cv2.threshold(img_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text_otsu_resized = pytesseract.image_to_string(otsu_resized)
        print("--- RESIZED OTSU OCR ---")
        print(repr(text_otsu_resized))
        
        # 4. Sweep thresholds on 2x resized
        for thresh in [80, 100, 110, 120, 130, 140, 150, 160]:
            _, thresh_img = cv2.threshold(img_resized, thresh, 255, cv2.THRESH_BINARY)
            text_t = pytesseract.image_to_string(thresh_img)
            print(f"--- RESIZED THRESH {thresh} OCR ---")
            print(repr(text_t[:300]))

if __name__ == "__main__":
    asyncio.run(main())
