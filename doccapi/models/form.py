from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class FormField(BaseModel):
    id: Optional[int] = None
    form_id: Optional[int] = None
    name: str
    label: Optional[str] = None
    field_type: str
    required: bool = False
    options: Optional[List[str]] = None
    order: int = 0

class Form(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    created_by: Optional[int] = None
    fields: Optional[List[FormField]] = []

class FormEntry(BaseModel):
    
    id: Optional[int] = None
    form_id: int
    user_id: Optional[int] = None
    data: Dict[str, Any]
    created_at: Optional[str] = None  # ISO format date string
    updated_at: Optional[str] = None  # ISO format date string
    status: str | None