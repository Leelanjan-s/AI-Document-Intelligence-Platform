from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import uuid

from app.db.database import get_db
from app.models.models import Document, WorkflowRun, AgentExecution, TokenUsage, User
from app.schemas.schemas import TokenUsageSummary, TokenUsageDetail, WorkflowRunMetric
from app.api.deps import get_current_user

router = APIRouter(prefix="/metrics", tags=["Metrics Dashboard"])

@router.get("/token-usage", response_model=TokenUsageSummary)
async def get_token_usage_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve summarized model token usages and running costs for the organization."""
    # Query aggregated cost and counts grouped by model_name
    query = (
        select(
            TokenUsage.model_name,
            func.sum(TokenUsage.prompt_tokens).label("prompt_tokens"),
            func.sum(TokenUsage.completion_tokens).label("completion_tokens"),
            func.sum(TokenUsage.cost).label("cost")
        )
        .where(TokenUsage.organization_id == current_user.organization_id)
        .group_by(TokenUsage.model_name)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    usage_details = []
    total_cost = 0.0
    
    for r in rows:
        cost = float(r.cost)
        total_cost += cost
        usage_details.append(
            TokenUsageDetail(
                model_name=r.model_name,
                prompt_tokens=int(r.prompt_tokens or 0),
                completion_tokens=int(r.completion_tokens or 0),
                cost=cost
            )
        )
        
    return TokenUsageSummary(
        total_cost=round(total_cost, 4),
        usage_by_model=usage_details
    )

@router.get("/workflows", response_model=WorkflowRunMetric)
async def get_workflow_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve throughput volumes, success ratios, and average latency metrics for document processing runs."""
    # 1. Volume and Status counts
    # Fetch all workflows for documents belonging to this organization
    wf_stmt = (
        select(
            WorkflowRun.status,
            func.count(WorkflowRun.id).label("count")
        )
        .join(Document, Document.id == WorkflowRun.document_id)
        .where(Document.organization_id == current_user.organization_id)
        .group_by(WorkflowRun.status)
    )
    
    wf_res = await db.execute(wf_stmt)
    wf_rows = wf_res.all()
    
    status_counts = {"running": 0, "completed": 0, "failed": 0, "review_needed": 0}
    total_runs = 0
    
    for r in wf_rows:
        status_counts[r.status] = int(r.count or 0)
        total_runs += int(r.count or 0)

    # 2. Average Latency (calculated from successfully finished AgentExecutions)
    latency_stmt = (
        select(
            func.avg(AgentExecution.latency_ms).label("avg_latency")
        )
        .join(WorkflowRun, WorkflowRun.id == AgentExecution.workflow_run_id)
        .join(Document, Document.id == WorkflowRun.document_id)
        .where(
            Document.organization_id == current_user.organization_id,
            AgentExecution.status == "success"
        )
    )
    
    lat_res = await db.execute(latency_stmt)
    avg_latency = lat_res.scalar() or 0.0
    
    return WorkflowRunMetric(
        total_runs=total_runs,
        completed_runs=status_counts.get("completed", 0),
        failed_runs=status_counts.get("failed", 0),
        review_needed_runs=status_counts.get("review_needed", 0),
        average_latency_ms=round(float(avg_latency), 2)
    )
