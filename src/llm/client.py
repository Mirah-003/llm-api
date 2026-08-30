import os
import json
import re
import time
import random
from openai import OpenAI, APIStatusError, APITimeoutError, AuthenticationError
from dotenv import load_dotenv
from pydantic import ValidationError

from src.llm.schema import TriageResponse
from src.llm.cache import global_cache

load_dotenv(override=True)

QUARANTINE_LOG = os.path.join("logs", "quarantine.jsonl")
COST_LOG = os.path.join("logs", "cost.jsonl")

class QuarantineException(Exception):
    """Raised when LLM output fails schema validation after repair retry."""
    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output

def load_system_prompt(prompt_version: str = "job-v1.md") -> str:
    """Reads a versioned system prompt specification from disk."""
    file_path = os.path.join("prompts", prompt_version)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Prompt file not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def strip_markdown_fences(text: str) -> str:
    """Strips ```json markdown code blocks and whitespace."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def log_quarantine(user_input: str, raw_output: str, error_msg: str, prompt_version: str):
    """Appends failed LLM attempts to logs/quarantine.jsonl."""
    os.makedirs("logs", exist_ok=True)
    entry = {
        "prompt_version": prompt_version,
        "input": user_input,
        "raw_output": raw_output,
        "error": error_msg,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    with open(QUARANTINE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def log_cost(model: str, prompt_version: str, input_tokens: int, output_tokens: int, duration_ms: float, was_repaired: bool, is_cached: bool = False):
    """Writes a structured cost & usage log line to logs/cost.jsonl."""
    os.makedirs("logs", exist_ok=True)
    cost_entry = {
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "duration_ms": round(duration_ms, 2),
        "was_repaired": was_repaired,
        "is_cached": is_cached,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    with open(COST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(cost_entry) + "\n")

def execute_llm_call_with_retry(client: OpenAI, model_name: str, messages: list):
    """Executes call with 30s timeout and retries ONLY 429/5xx errors."""
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                temperature=0.0,
                response_format={"type": "json_object"},  # Schema-constrained output request
                messages=messages
            )
            return response
        except (AuthenticationError, APIStatusError) as e:
            status_code = getattr(e, "status_code", None)
            if status_code in (401, 403, 400):
                print(f"🛑 Fail-Fast triggered for HTTP {status_code}: No retries performed.")
                raise e
            if attempt < max_retries and (status_code == 429 or (status_code and status_code >= 500)):
                sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
            else:
                raise e
        except APITimeoutError as te:
            if attempt < max_retries:
                sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
            else:
                raise te

def process_triage_request(user_input: str, prompt_version: str = "job-v1.md", use_cache: bool = True) -> TriageResponse:
    """
    Complete Pipeline with Response Caching:
    Cache Check -> Call -> Parse -> Validate -> Repair Once -> Log Cost -> Quarantine
    """
    # 1. CHECK CACHE FIRST
    if use_cache:
        cached_response = global_cache.get(prompt_version, user_input)
        if cached_response:
            print(f"⚡ CACHE HIT for query: '{user_input[:30]}...'")
            log_cost("cache-hit", prompt_version, 0, 0, 0.5, was_repaired=False, is_cached=True)
            return cached_response

    # 2. CACHE MISS: Call Model
    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY"),
        timeout=30.0,
        max_retries=0
    )
    
    system_prompt = load_system_prompt(prompt_version)
    model_name = os.environ.get("LLM_MODEL", "openrouter/free")

    # OWASP Protection: Wrap user input cleanly inside quotes
    safe_user_content = f'Customer Message Content:\n"""\n{user_input}\n"""'

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": safe_user_content}
    ]

    start_time = time.perf_counter()
    input_tokens = 0
    output_tokens = 0

    # --- ATTEMPT 1 ---
    res1 = execute_llm_call_with_retry(client, model_name, messages)
    raw_output1 = res1.choices[0].message.content
    cleaned_output1 = strip_markdown_fences(raw_output1)

    if hasattr(res1, "usage") and res1.usage:
        input_tokens += res1.usage.prompt_tokens
        output_tokens += res1.usage.completion_tokens

    try:
        validated_response = TriageResponse.model_validate_json(cleaned_output1)
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_cost(model_name, prompt_version, input_tokens, output_tokens, duration_ms, was_repaired=False)
        
        # Save to cache on success
        if use_cache:
            global_cache.set(prompt_version, user_input, validated_response)
        return validated_response
    except ValidationError as err1:
        error_details = str(err1)
        print(f"⚠️ Validation Failed: {error_details}. Initiating Repair Retry...")

    # --- ATTEMPT 2: REPAIR RETRY ---
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

    try:
        validated_response = TriageResponse.model_validate_json(cleaned_output2)
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_cost(model_name, prompt_version, input_tokens, output_tokens, duration_ms, was_repaired=True)
        
        if use_cache:
            global_cache.set(prompt_version, user_input, validated_response)
        return validated_response
    except ValidationError as err2:
        final_error = f"Repair retry failed: {str(err2)}"
        log_quarantine(user_input, raw_output2, final_error, prompt_version)
        raise QuarantineException(message=final_error, raw_output=raw_output2)