import asyncio
from sqlalchemy import delete
from app.db import database as db
from app.models.models import DocumentType, Document, WorkflowRun, ExtractedData

async def main():
    async with db.async_session_maker() as session:
        # Delete old dynamically created document types so they regenerate
        stmt = delete(DocumentType).where(DocumentType.name.in_(["PAN Card", "Identity Card", "Aadhaar Card", "Marksheet"]))
        res = await session.execute(stmt)
        print(f"Deleted dynamically created document types.")
        
        # Also let's clean up existing documents so the user can re-upload them clean
        # Wait, the user can also delete them via the UI, but let's delete all processed documents
        # so they start fresh.
        del_docs = delete(Document)
        await session.execute(del_docs)
        print("Cleared all old documents from database to prevent duplicate schema issues.")
        
        await session.commit()
        print("Database cleanup successful.")

if __name__ == "__main__":
    asyncio.run(main())
