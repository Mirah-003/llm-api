import os
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

from src.llm.schema import TriageRequest, TriageResponse, CategoryEnum, UrgencyEnum
from src.llm.client import process_triage_request, QuarantineException

load_dotenv(override=True)
app = FastAPI(title="LLM Triage API")

# Custom Exception Handler: Overrides default 422 to return HTTP 400 when user input is invalid
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    field_name = errors[0]["loc"][-1] if errors else "body"
    msg = errors[0]["msg"] if errors else "Invalid request body"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": f"Validation error on field '{field_name}': {msg}"}
    )

@app.post("/triage", response_model=TriageResponse)
async def triage_endpoint(payload: TriageRequest):
    """
    Classifies an incoming customer support message.
    Returns clean, validated JSON matching TriageResponse schema.
    """
    # 1. STUB MODE CHECK: Bypasses LLM calls when LLM_STUB=1
    if os.environ.get("LLM_STUB") == "1":
        return TriageResponse(
            category=CategoryEnum.BUG,
            urgency=UrgencyEnum.HIGH,
            confidence=0.95,
            reason="[STUB] High urgency bug report detected."
        )

    # 2. REAL AI CALL: Executes Parse -> Validate -> Repair -> Quarantine Pipeline
    try:
        validated_data = process_triage_request(payload.text)
        return validated_data
    except QuarantineException as qe:
        # Give up cleanly with HTTP 422 (Unprocessable Entity) when model output fails validation
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Model failed to produce a valid schema-compliant response after repair retry.",
                "quarantined_output": qe.raw_output
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Server Error: {str(e)}"}
        )