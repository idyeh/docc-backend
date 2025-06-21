from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class Workflow(BaseModel):
    id: Optional[int] = None
    name: str
    steps: List[Dict[str, Any]]


class Workflowinstance(BaseModel):
    id: Optional[int] = None
    workflow_id: Optional[int] = None
    workflow_name: Optional[str] = None
    user_id: Optional[int] = None
    form_id: Optional[int] = None
    entity_type: str
    entity_id: int
    current_step: Optional[int] = 0
    state: Optional[str] = None
    logs: Optional[List[Dict[str, Any]]] = []


class Log(BaseModel):
    comment: str
    action: str