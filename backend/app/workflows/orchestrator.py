import uuid
import traceback
from datetime import datetime
from typing import Dict, Any
from loguru import logger
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.nodes import ocr_agent, classification_agent, extraction_agent, validation_agent, confidence_agent
from app.db import database as db
from app.models.models import Document, WorkflowRun
from sqlalchemy import update

# Initialize State Graph
builder = StateGraph(AgentState)

# Add Nodes
builder.add_node("ocr", ocr_agent)
builder.add_node("classification", classification_agent)
builder.add_node("extraction", extraction_agent)
builder.add_node("validation", validation_agent)
builder.add_node("confidence", confidence_agent)

# Set Entry Point
builder.set_entry_point("ocr")

# Define Edges
builder.add_edge("ocr", "classification")
builder.add_edge("classification", "extraction")
builder.add_edge("extraction", "validation")
builder.add_edge("validation", "confidence")
builder.add_edge("confidence", END)

# Compile Graph
workflow_graph = builder.compile()

class WorkflowOrchestrator:
    @staticmethod
    async def run_document_workflow(document_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """Orchestrates the running of the LangGraph agent state machine for a document."""
        logger.info(f"Starting workflow orchestration for document {document_id}")
        
        # 1. Create a WorkflowRun record
        workflow_run_id = uuid.uuid4()
        async with db.async_session_maker() as session:
            wf_run = WorkflowRun(
                id=workflow_run_id,
                document_id=document_id,
                status="running",
                current_step="initialized",
                started_at=datetime.utcnow()
            )
            session.add(wf_run)
            
            # Update Document status to processing
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status="processing")
            )
            await session.commit()
            
        # 2. Invoke LangGraph
        initial_state: AgentState = {
            "document_id": str(document_id),
            "organization_id": str(org_id),
            "user_id": str(user_id),
            "raw_text": "",
            "classification": "",
            "extracted_data": {},
            "validation_results": {},
            "confidence_score": 0.0,
            "confidence_rationale": "",
            "errors": [],
            "status": "processing",
            "token_usage": []
        }
        
        try:
            # Execute the compiled graph asynchronously
            # We wrap the invocation to execute on the asyncio event loop
            final_state = await workflow_graph.ainvoke(initial_state)
            logger.info(f"Workflow execution completed for document {document_id} with status: {final_state.get('status')}")
            return final_state
            
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Workflow run failed for document {document_id}: {e}\n{tb}")
            
            # Persist failure details
            async with db.async_session_maker() as session:
                await session.execute(
                    update(WorkflowRun)
                    .where(WorkflowRun.id == workflow_run_id)
                    .values(
                        status="failed",
                        error_message=str(e)[:1000],
                        completed_at=datetime.utcnow()
                    )
                )
                await session.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status="failed")
                )
                await session.commit()
                
            return {
                "document_id": str(document_id),
                "errors": [str(e)],
                "status": "failed"
            }

orchestrator = WorkflowOrchestrator()
