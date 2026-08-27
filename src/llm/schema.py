from enum import Enum
from pydantic import BaseModel, Field

# 1. Closed Lists (Enums) - The AI can ONLY pick values from these lists!
class CategoryEnum(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"

class UrgencyEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

# 2. Input Schema (What the user sends to our API)
class TriageRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=2000, 
        description="The customer support message to triage"
    )

# 3. Output Schema (What our API and the AI must return)
class TriageResponse(BaseModel):
    category: CategoryEnum
    urgency: UrgencyEnum
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reason: str = Field(..., description="One short sentence explaining the categorization")