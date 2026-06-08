from typing import TypedDict, Dict, Any, List, Optional

class AgentState(TypedDict):
    document_id: str
    organization_id: str
    user_id: str
    raw_text: Optional[str]
    classification: Optional[str]
    extracted_data: Optional[Dict[str, Any]]
    validation_results: Optional[Dict[str, Any]]  # {"is_valid": bool, "missing_fields": list, "errors": list}
    confidence_score: Optional[float]
    confidence_rationale: Optional[str]
    errors: List[str]
    status: str  # processing, review_needed, completed, failed
    token_usage: List[Dict[str, Any]]  # [{"model": str, "prompt_tokens": int, "completion_tokens": int, "cost": float}]
