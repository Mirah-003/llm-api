from enum import Enum
from pydantic import BaseModel, Field

# ==========================================
# TODO 1 — Output & Input Schema Definitions
# ==========================================
# PSEUDOCODE / CONTRACT:
# 1. Define closed Enums for category and urgency to prevent arbitrary free-text values.
# 2. Define TriageRequest schema to validate incoming input text (min 1 char, max 2000).
# 3. Define TriageResponse schema to validate outgoing LLM decisions.
# ==========================================

class CategoryEnum(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"

class UrgencyEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

class TriageRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=2000, 
        description="The customer support message to triage"
    )

class TriageResponse(BaseModel):
    category: CategoryEnum
    urgency: UrgencyEnum
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reason: str = Field(..., description="One short sentence explaining the categorization")