import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

# Points to your prompt file
PROMPT_FILE = os.path.join("prompts", "job-v1.md")

def load_system_prompt() -> str:
    """Reads the versioned system prompt specification from disk."""
    if not os.path.exists(PROMPT_FILE):
        raise FileNotFoundError(f"Prompt file not found at {PROMPT_FILE}")
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def call_llm(user_input: str) -> str:
    """
    Sends system prompt and untrusted user input to OpenRouter.
    Returns the raw model output string.
    """
    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY")
    )
    
    system_prompt = load_system_prompt()
    model_name = os.environ.get("LLM_MODEL", "openrouter/free")

    # STRICT SEPARATION: system prompt vs untrusted user message
    response = client.chat.completions.create(
        model=model_name,
        temperature=0.0,  # Low temperature for deterministic output
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    
    return response.choices[0].message.content