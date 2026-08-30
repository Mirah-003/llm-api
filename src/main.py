import os
import json
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from openai import APITimeoutError, AuthenticationError
from dotenv import load_dotenv

from src.llm.schema import TriageRequest, TriageResponse, CategoryEnum, UrgencyEnum
from src.llm.client import process_triage_request, QuarantineException
from src.llm.cache import global_cache

load_dotenv(override=True)
app = FastAPI(title="LLM Triage API")

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
    load_dotenv(override=True)

    # 1. KILL SWITCH CHECK
    llm_enabled = os.environ.get("LLM_ENABLED", "true").lower()
    if llm_enabled in ("false", "0", "no"):
        return TriageResponse(
            category=CategoryEnum.OTHER,
            urgency=UrgencyEnum.LOW,
            confidence=0.0,
            reason="[KILL SWITCH] AI service is currently disabled. Deterministic fallback returned."
        )

    # 2. STUB MODE CHECK
    if os.environ.get("LLM_STUB") == "1":
        return TriageResponse(
            category=CategoryEnum.BUG,
            urgency=UrgencyEnum.HIGH,
            confidence=0.95,
            reason="[STUB] High urgency bug report detected."
        )

    # 3. PRODUCTION AI EXECUTION PIPELINE
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
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication failed: Invalid API Key. No retries performed."}
        )
    except APITimeoutError:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "LLM request timed out after 30.0 seconds."}
        )
    except Exception as e:
        # Log the full error server-side for debugging, but never expose internals to callers
        print(f"🔥 Unhandled server error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error. Check server logs for details."}
        )

# ==========================================
# BONUS EXTRA — GET /metrics Endpoint
# ==========================================
@app.get("/metrics")
async def get_observability_metrics():
    """
    Observability Endpoint:
    Parses logs/cost.jsonl and returns live aggregate system metrics.
    """
    cost_log_path = os.path.join("logs", "cost.jsonl")
    total_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0.0
    repair_count = 0

    if os.path.exists(cost_log_path):
        with open(cost_log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                total_calls += 1
                total_input_tokens += data.get("input_tokens", 0)
                total_output_tokens += data.get("output_tokens", 0)
                total_duration_ms += data.get("duration_ms", 0.0)
                if data.get("was_repaired"):
                    repair_count += 1

    avg_latency_ms = round(total_duration_ms / total_calls, 2) if total_calls > 0 else 0.0

    return {
        "status": "healthy",
        "cache_stats": global_cache.get_stats(),
        "observability": {
            "total_logged_calls": total_calls,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "avg_latency_ms": avg_latency_ms,
            "repairs_triggered": repair_count
        }
    }