import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError

from src.llm.schema import TriageResponse

load_dotenv(override=True)

PROMPT_FILE = os.path.join("prompts", "job-v1.md")
QUARANTINE_LOG = os.path.join("logs", "quarantine.jsonl")

class QuarantineException(Exception):
    """Custom exception raised when LLM output fails schema validation after repair retry."""
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
    """Strips ```json markdown code blocks and leading/trailing whitespace."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def log_quarantine(user_input: str, raw_output: str, error_msg: str):
    """Appends failed LLM attempts to logs/quarantine.jsonl."""
    os.makedirs("logs", exist_ok=True)
    quarantine_entry = {
        "prompt_version": "job-v1.md",
        "input": user_input,
        "raw_output": raw_output,
        "error": error_msg
    }
    with open(QUARANTINE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(quarantine_entry) + "\n")

def process_triage_request(user_input: str) -> TriageResponse:
    """
    Executes the complete LLM pipeline:
    Call -> Parse -> Validate -> Repair Once -> Quarantine on Failure
    """
    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY")
    )
    
    system_prompt = load_system_prompt()
    model_name = os.environ.get("LLM_MODEL", "openrouter/free")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    # --- ATTEMPT 1: Initial Model Call ---
    res1 = client.chat.completions.create(
        model=model_name,
        temperature=0.0,
        messages=messages
    )
    raw_output1 = res1.choices[0].message.content
    cleaned_output1 = strip_markdown_fences(raw_output1)

    # Validate Attempt 1 against Pydantic schema
    try:
        validated_response = TriageResponse.model_validate_json(cleaned_output1)
        return validated_response
    except (ValidationError, Exception) as err1:
        error_details = str(err1)
        print(f"⚠️ Attempt 1 Validation Failed: {error_details}. Initiating Repair Retry...")

    # --- ATTEMPT 2: Repair Retry (Exactly One Repair Attempt) ---
    messages.append({"role": "assistant", "content": raw_output1})
    messages.append({
        "role": "user", 
        "content": f"Your previous answer was rejected for this validation error: {error_details}. Return ONLY corrected raw JSON matching the schema."
    })

    res2 = client.chat.completions.create(
        model=model_name,
        temperature=0.0,
        messages=messages
    )
    raw_output2 = res2.choices[0].message.content
    cleaned_output2 = strip_markdown_fences(raw_output2)

    # Validate Attempt 2
    try:
        validated_response = TriageResponse.model_validate_json(cleaned_output2)
        return validated_response
    except (ValidationError, Exception) as err2:
        # --- GIVE UP CLEANLY & QUARANTINE ---
        final_error = f"Repair retry failed: {str(err2)}"
        log_quarantine(user_input, raw_output2, final_error)
        raise QuarantineException(message=final_error, raw_output=raw_output2)