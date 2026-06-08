import asyncio
import os
import fitz
from PIL import Image
import io
from app.agents.nodes import run_tesseract_ocr

async def main():
    base_dir = "/Users/leelanjan/AI_Document_Intelligence/AI-Document-Intelligence-Platform/backend/local_storage/raw/e6855f08-bac6-4eb3-9e36-b39b791681b8"
    files = {
        "Aadhaar": ("dc9e5074-b4ba-4c5e-95e5-40c4b1373ebb.pdf", "ADDAR LEELANJAN.pdf"),
        "PAN": ("9a6dd4da-2792-43d5-a195-7309eb38d990.pdf", "pan card leelanjan.pdf"),
        "Marksheet": ("d908f92d-b48b-4e82-8c1f-6b277761275b.pdf", "B.E ALL SEM RESULT.pdf"),
        "10th": ("483fc290-c41d-4fd8-9c25-4ff05ec2ab9d.pdf", "10TH MARKS CARD LEELANJAN.pdf")
    }
    
    for name, (file_uuid, filename) in files.items():
        file_path = os.path.join(base_dir, file_uuid)
        print(f"\n==========================================")
        print(f"OCR FOR {name} ({filename})")
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        if filename.lower().endswith(".pdf"):
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            for idx, page in enumerate(pdf_doc):
                text = page.get_text()
                print(f"Page {idx} Selectable Text (len={len(text)}):")
                print(repr(text[:300]))
                
                # Check if we should do OCR
                is_cert = "cert" in filename.lower() or "marks" in filename.lower() or "result" in filename.lower() or "sem" in filename.lower()
                if (is_cert and len(text.strip()) < 150) or not text.strip():
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = run_tesseract_ocr(img)
                    print(f"Page {idx} OCR Text (len={len(ocr_text)}):")
                    print(ocr_text[:1000])
        else:
            img = Image.open(io.BytesIO(file_bytes))
            ocr_text = run_tesseract_ocr(img)
            print(f"OCR Text (len={len(ocr_text)}):")
            print(ocr_text[:1000])

if __name__ == "__main__":
    asyncio.run(main())
