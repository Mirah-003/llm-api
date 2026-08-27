import os
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from openai import APITimeoutError, AuthenticationError
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
    Supports Kill Switch (LLM_ENABLED=false), Stub Mode (LLM_STUB=1), and Production AI execution.
    """
    # LINE 30: Force Python to re-read .env on every incoming request
    load_dotenv(override=True)

    # LINE 32: KILL SWITCH CHECK (LLM_ENABLED=false skips LLM calls entirely)
    llm_enabled = os.environ.get("LLM_ENABLED", "true").lower()
    if llm_enabled in ("false", "0", "no"):
        return TriageResponse(
            category=CategoryEnum.OTHER,
            urgency=UrgencyEnum.LOW,
            confidence=0.0,
            reason="[KILL SWITCH] AI service is currently disabled. Deterministic fallback returned."
        )

    # STUB MODE CHECK
    if os.environ.get("LLM_STUB") == "1":
        return TriageResponse(
            category=CategoryEnum.BUG,
            urgency=UrgencyEnum.HIGH,
            confidence=0.95,
            reason="[STUB] High urgency bug report detected."
        )

    # PRODUCTION AI EXECUTION
    try:
        validated_data = process_triage_request(payload.text)
        return validated_data
    except QuarantineException as qe:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Model failed to produce a valid schema-compliant response after repair retry.",
                "quarantined_output": qe.raw_output
            }
        )
    except AuthenticationError:
        # HTTP 401 Unauthorized when API Key is invalid
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication failed: Invalid API Key. No retries performed."}
        )
    except APITimeoutError:
        # HTTP 504 Gateway Timeout when model call exceeds 30.0s
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "LLM request timed out after 30.0 seconds."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Server Error: {str(e)}"}
        )