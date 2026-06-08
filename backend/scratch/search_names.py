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
        
        storage.ensure_bucket_exists()
        file_bytes = await storage.download_file_bytes(doc.storage_path)
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        page = pdf_doc[0]
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        ocr_text = run_tesseract_ocr(img)
        
        print("\n=== FILTERED OCR LINES ===")
        for line in ocr_text.split("\n"):
            line_clean = line.strip()
            if not line_clean:
                continue
            lower = line_clean.lower()
            if any(k in lower for k in ["name", "father", "mother", "candidate", "student", "roll", "reg", "no", "number", "leela", "sathish", "leelanjan"]):
                print(repr(line_clean))

if __name__ == "__main__":
    asyncio.run(main())
