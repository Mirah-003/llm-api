import os
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

from src.llm.schema import TriageRequest, TriageResponse, CategoryEnum, UrgencyEnum
from src.llm.client import call_llm

load_dotenv(override=True)
app = FastAPI(title="LLM Triage API")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom validation handler to return HTTP 400 with field details."""
    errors = exc.errors()
    field_name = errors[0]["loc"][-1] if errors else "body"
    msg = errors[0]["msg"] if errors else "Invalid request body"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": f"Validation error on field '{field_name}': {msg}"}
    )

@app.post("/triage")
async def triage_endpoint(payload: TriageRequest):
    """
    Classifies an incoming customer support message.
    When LLM_STUB=1, returns a mock response without calling the model.
    When LLM_STUB=0, calls OpenRouter with prompts/job-v1.md.
    """
    if os.environ.get("LLM_STUB") == "1":
        return TriageResponse(
            category=CategoryEnum.BUG,
            urgency=UrgencyEnum.HIGH,
            confidence=0.95,
            reason="[STUB] High urgency bug report detected."
        )

    try:
        raw_output = call_llm(payload.text)
        return {"raw_output": raw_output}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"LLM Call Failed: {str(e)}"}
        )