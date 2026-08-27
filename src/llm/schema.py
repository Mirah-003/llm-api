from enum import Enum
from pydantic import BaseModel, Field

# Enums define strict closed lists for classification categories
class CategoryEnum(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"

class UrgencyEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

# Request Schema: Validates incoming request payload
class TriageRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=2000, 
        description="The customer support message to triage"
    )

# Response Schema: Validates outgoing LLM decision payload
class TriageResponse(BaseModel):
    category: CategoryEnum
    urgency: UrgencyEnum
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reason: str = Field(..., description="One short sentence explaining the categorization")