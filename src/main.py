# ==========================================
# FLYRANK AI — ASSIGNMENT BE-06: PUT AN LLM BEHIND YOUR API
# ==========================================

# ------------------------------------------
# 1. IMPORTS (Always at the very top!)
# ------------------------------------------
import os
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

# Local application imports
from src.llm.schema import TriageRequest, TriageResponse, CategoryEnum, UrgencyEnum


# ------------------------------------------
# 2. INITIALIZATION & CONFIGURATION
# ------------------------------------------
load_dotenv(override=True)
app = FastAPI(title="LLM Triage API")


# ==========================================
# TODO 0 — Custom Exception Handlers
# ==========================================
# - Override FastAPI default validation handler to return HTTP 400 instead of 422
# ==========================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    field_name = errors[0]["loc"][-1] if errors else "body"
    msg = errors[0]["msg"] if errors else "Invalid request body"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": f"Validation error on field '{field_name}': {msg}"}
    )


# ==========================================
# TODO 1 — Route Handler & Stub Mode (POST /triage)
# ==========================================

@app.post("/triage", response_model=TriageResponse)
async def triage_endpoint(payload: TriageRequest):
    """
    Classifies an incoming customer support message.
    When LLM_STUB=1, returns a mock response without calling the model.
    """
    # 1. STUB MODE CHECK
    if os.environ.get("LLM_STUB") == "1":
        return TriageResponse(
            category=CategoryEnum.BUG,
            urgency=UrgencyEnum.HIGH,
            confidence=0.95,
            reason="[STUB] High urgency bug report detected."
        )

    # Real AI call will be connected here in Stage 3!
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED, 
        content={"detail": "Real LLM calls not implemented yet. Set LLM_STUB=1 in .env to test stub mode."}
    )