# Pydantic schemas for TriageResult and ValidatedTriage
from pydantic import BaseModel, Field
from typing import List, Optional

class TriageResult(BaseModel):
    category: str = Field(description="The category of the issue")
    priority: int = Field(description="Priority level from 1 to 5")
    summary: str = Field(description="A brief summary of the request")

class ValidatedTriage(TriageResult):
    is_valid: bool = Field(description="Indicates if the validation passed")
    notes: Optional[str] = Field(description="Validation notes or remarks")
