import os
import json
import re
import time
import random
from openai import OpenAI, APIStatusError, APITimeoutError, AuthenticationError
from dotenv import load_dotenv
from pydantic import ValidationError

from src.llm.schema import TriageResponse

load_dotenv(override=True)

PROMPT_FILE = os.path.join("prompts", "job-v1.md")
QUARANTINE_LOG = os.path.join("logs", "quarantine.jsonl")
COST_LOG = os.path.join("logs", "cost.jsonl")

class QuarantineException(Exception):
    """Raised when LLM output fails schema validation after repair retry."""
    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output

def load_system_prompt() -> str:
    """Reads the versioned system prompt specification from disk."""
    if not os.path.exists(PROMPT_FILE):
        raise FileNotFoundError(f"Prompt file not found at {PROMPT_FILE}")
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def strip_markdown_fences(text: str) -> str:
    """Strips ```json markdown code blocks and whitespace."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def log_quarantine(user_input: str, raw_output: str, error_msg: str):
    """Appends failed LLM attempts to logs/quarantine.jsonl."""
    os.makedirs("logs", exist_ok=True)
    entry = {
        "prompt_version": "job-v1.md",
        "input": user_input,
        "raw_output": raw_output,
        "error": error_msg,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    with open(QUARANTINE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def log_cost(model: str, input_tokens: int, output_tokens: int, duration_ms: float, was_repaired: bool):
    """Writes a structured cost & usage log line to logs/cost.jsonl."""
    os.makedirs("logs", exist_ok=True)
    cost_entry = {
        "prompt_version": "job-v1.md",
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "duration_ms": round(duration_ms, 2),
        "was_repaired": was_repaired,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    with open(COST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(cost_entry) + "\n")

def execute_llm_call_with_retry(client: OpenAI, model_name: str, messages: list):
    """
    Executes LLM call with explicit timeout (30s) and exponential backoff retry.
    Retries ONLY on 429 rate limits, 5xx server errors, or timeouts.
    FAILS FAST on 401 (Authentication), 403, or 400 errors without retrying!
    """
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                temperature=0.0,
                messages=messages
            )
            return response
        except (AuthenticationError, APIStatusError) as e:
            status_code = getattr(e, "status_code", None)
            # FAIL FAST: Never retry 401, 403, or 400 errors!
            if status_code in (401, 403, 400):
                print(f"🛑 Fail-Fast triggered for HTTP {status_code}: No retries performed.")
                raise e
            # Retry on 429 or 5xx errors with backoff + jitter
            if attempt < max_retries and (status_code == 429 or (status_code and status_code >= 500)):
                sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                print(f"⚠️ HTTP {status_code} detected. Retrying in {sleep_time:.2f}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(sleep_time)
            else:
                raise e
        except APITimeoutError as te:
            if attempt < max_retries:
                sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                print(f"⚠️ Timeout detected. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            else:
                raise te

def process_triage_request(user_input: str) -> TriageResponse:
    """
    Production Pipeline:
    Call (Timeout=30s, Retries=429/5xx only) -> Parse -> Validate -> Repair Once -> Log Cost -> Quarantine
    """
    # 1. Instantiate OpenAI client with explicit 30.0s timeout and max_retries=0
    # (We handle custom retries explicitly above to enforce selective fail-fast on 401!)
    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY"),
        timeout=30.0,
        max_retries=0
    )
    
    system_prompt = load_system_prompt()
    model_name = os.environ.get("LLM_MODEL", "openrouter/free")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    start_time = time.perf_counter()
    input_tokens = 0
    output_tokens = 0
    was_repaired = False

    # --- ATTEMPT 1: Initial Call ---
    res1 = execute_llm_call_with_retry(client, model_name, messages)
    raw_output1 = res1.choices[0].message.content
    cleaned_output1 = strip_markdown_fences(raw_output1)

    if hasattr(res1, "usage") and res1.usage:
        input_tokens += res1.usage.prompt_tokens
        output_tokens += res1.usage.completion_tokens

    # Validate Attempt 1
    try:
        validated_response = TriageResponse.model_validate_json(cleaned_output1)
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_cost(model_name, input_tokens, output_tokens, duration_ms, was_repaired=False)
        return validated_response
    except (ValidationError, Exception) as err1:
        error_details = str(err1)
        was_repaired = True
        print(f"⚠️ Validation Failed: {error_details}. Initiating Repair Retry...")

    # --- ATTEMPT 2: Repair Retry ---
    messages.append({"role": "assistant", "content": raw_output1})
    messages.append({
        "role": "user", 
        "content": f"Your previous answer was rejected for this validation error: {error_details}. Return ONLY corrected raw JSON matching the schema."
    })

    res2 = execute_llm_call_with_retry(client, model_name, messages)
    raw_output2 = res2.choices[0].message.content
    cleaned_output2 = strip_markdown_fences(raw_output2)

    if hasattr(res2, "usage") and res2.usage:
        input_tokens += res2.usage.prompt_tokens
        output_tokens += res2.usage.completion_tokens

    # Validate Attempt 2
    try:
        validated_response = TriageResponse.model_validate_json(cleaned_output2)
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_cost(model_name, input_tokens, output_tokens, duration_ms, was_repaired=True)
        return validated_response
    except (ValidationError, Exception) as err2:
        # Give up cleanly and quarantine
        final_error = f"Repair retry failed: {str(err2)}"
        log_quarantine(user_input, raw_output2, final_error)
        raise QuarantineException(message=final_error, raw_output=raw_output2)