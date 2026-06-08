import asyncio
from sqlalchemy import select
from app.db import database as db
from app.models.models import Document, WorkflowRun, AgentExecution, ExtractedData

async def main():
    async with db.async_session_maker() as session:
        doc_stmt = select(Document).order_by(Document.created_at.desc()).limit(8)
        doc_res = await session.execute(doc_stmt)
        docs = doc_res.scalars().all()
        
        for idx, doc in enumerate(docs):
            print(f"\n==================================================")
            print(f"[{idx+1}] ID: {doc.id} | Name: {doc.name}")
            print(f"Status: {doc.status} | Conf: {doc.confidence_score}")
            
            # Find workflow runs
            wf_stmt = select(WorkflowRun).where(WorkflowRun.document_id == doc.id).order_by(WorkflowRun.started_at.desc())
            wf_res = await session.execute(wf_stmt)
            wf = wf_res.scalars().first()
            if not wf:
                print("No workflow run found")
                continue
                
            # Get OCR agent execution output (raw text)
            ae_stmt = select(AgentExecution).where(
                AgentExecution.workflow_run_id == wf.id,
                AgentExecution.agent_name == "ocr_agent"
            )
            ae_res = await session.execute(ae_stmt)
            ae = ae_res.scalar_one_or_none()
            if ae and ae.output_data:
                # Let's get raw text from state if possible, or print output metadata
                print(f"OCR Method: {ae.output_data.get('method')}")
            
            # Let's get classification agent output
            ae_class_stmt = select(AgentExecution).where(
                AgentExecution.workflow_run_id == wf.id,
                AgentExecution.agent_name == "classification_agent"
            )
            ae_class_res = await session.execute(ae_class_stmt)
            ae_class = ae_class_res.scalar_one_or_none()
            if ae_class:
                print(f"Classification Output: {ae_class.output_data}")
            
            # Extracted data
            ext_stmt = select(ExtractedData).where(ExtractedData.document_id == doc.id)
            ext_res = await session.execute(ext_stmt)
            ext = ext_res.scalar_one_or_none()
            if ext:
                print(f"Extracted Data: {ext.data}")
            
            # Print raw text if available in workflow run state
            # The raw text is stored in state.py/AgentState, which is passed between nodes,
            # and may be present in classification_agent's input_data
            if ae_class and ae_class.input_data:
                raw_txt = ae_class.input_data.get("raw_text", "")
                if not raw_txt and "text_len" in ae_class.input_data:
                    # check other inputs/outputs
                    pass
                print("--- RAW TEXT START (First 1500 chars) ---")
                # Wait, where is the text stored? Let's check AgentExecution input_data/output_data
                # We can print input_data or output_data of extraction_agent / ocr_agent
                if ae and ae.output_data:
                    # Let's download the original file or check if we logged raw_text
                    pass
                # Let's inspect the input data of extraction_agent
                ae_ext_stmt = select(AgentExecution).where(
                    AgentExecution.workflow_run_id == wf.id,
                    AgentExecution.agent_name == "extraction_agent"
                )
                ae_ext_res = await session.execute(ae_ext_stmt)
                ae_ext = ae_ext_res.scalar_one_or_none()
                if ae_ext and ae_ext.input_data:
                    # We might have text in input_data. Let's see keys
                    print("Extraction Input keys:", ae_ext.input_data.keys())
            
            # If we don't have the raw text logged, we can print it by rerunning the OCR agent or downloading the file.
            # Let's do that for the files in the next step if needed.

if __name__ == "__main__":
    asyncio.run(main())
