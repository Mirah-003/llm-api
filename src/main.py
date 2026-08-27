# ==========================================
# FLYRANK AI — ASSIGNMENT BE-06: PUT AN LLM BEHIND YOUR API
# ==========================================

# ==========================================
# TODO 1 — Pydantic Output Schema (src/llm/schema.py)
# ==========================================
# PSEUDOCODE:
# Define your structured output shape.
# - Create Enums for any closed lists (e.g., CategoryEnum).
# - Create a Pydantic BaseModel (e.g., LLMResponse) containing the required fields.
#
# RESEARCH:
# - Python Enum class.
# - Pydantic BaseModel.

# ==========================================
# TODO 2 & 3 — The Call & Repair Loop (src/llm/client.py)
# ==========================================
# PSEUDOCODE:
# Function: process_llm_request(user_input: str)
# 
# 1. Check Kill Switch:
#    - If LLM_ENABLED == false, return a safe fallback or raise 503 Service Unavailable.
#
# 2. Check Stub Mode:
#    - If LLM_STUB == 1, return a fake Pydantic object instantly.
#
# 3. Prepare the prompt:
#    - Read prompt string from `prompts/<job>-v1.md`.
#    - Setup messages array: [{"role": "system", "content": prompt}, {"role": "user", "content": user_input}]
#
# 4. First Attempt:
#    - Call the LLM client (with strict timeout configured).
#    - Extract the text content from the response.
#    - Strip any markdown code fences (e.g., remove ```json and ```).
#    - Try to parse and validate using LLMResponse.model_validate_json(text).
#    - If successful, return the parsed object!
#
# 5. The Repair Retry (If First Attempt Failed Validation):
#    - Catch the validation error.
#    - Append the bad response to the messages array: {"role": "assistant", "content": bad_text}
#    - Append the error to the messages array: {"role": "user", "content": f"Validation failed: {error}. Fix this and return ONLY valid JSON."}
#    - Call the LLM client a second time.
#    - Strip markdown fences and attempt validation again.
#    
# 6. Quarantine (If Second Attempt Fails):
#    - If validation fails again, do NOT crash.
#    - Log the raw input, raw output, and prompt version to a quarantine log (or print to stdout).
#    - Raise an HTTPException(status_code=422) indicating the model failed to produce valid output.