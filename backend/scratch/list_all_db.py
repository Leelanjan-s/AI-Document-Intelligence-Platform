import asyncio
from sqlalchemy import select
from app.db import database as db
from app.models.models import Document, WorkflowRun, ExtractedData

async def main():
    async with db.async_session_maker() as session:
        doc_stmt = select(Document).order_by(Document.created_at.desc())
        doc_res = await session.execute(doc_stmt)
        docs = doc_res.scalars().all()
        
        print(f"Total documents in database: {len(docs)}")
        for idx, doc in enumerate(docs):
            print(f"\n[{idx+1}] ID: {doc.id}")
            print(f"    Name: {doc.name}")
            print(f"    Mime-Type: {doc.mime_type}")
            print(f"    Status: {doc.status}")
            print(f"    Confidence: {doc.confidence_score}")
            print(f"    Created At: {doc.created_at}")
            
            # Find workflow runs
            wf_stmt = select(WorkflowRun).where(WorkflowRun.document_id == doc.id).order_by(WorkflowRun.started_at.desc())
            wf_res = await session.execute(wf_stmt)
            wf = wf_res.scalars().first()
            if wf:
                print(f"    Workflow Run: {wf.id} | Status: {wf.status} | Step: {wf.current_step}")
                if wf.error_message:
                    print(f"      Error: {wf.error_message}")
            
            # Find extracted data
            ext_stmt = select(ExtractedData).where(ExtractedData.document_id == doc.id)
            ext_res = await session.execute(ext_stmt)
            ext = ext_res.scalar_one_or_none()
            if ext:
                print(f"    Extracted Data: {ext.data}")
            else:
                print("    Extracted Data: None")

if __name__ == "__main__":
    asyncio.run(main())
