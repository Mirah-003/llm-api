import os
from dotenv import load_dotenv
from openai import OpenAI

# 1. Force reload the latest values from .env
load_dotenv(override=True)

model_name = os.environ.get("LLM_MODEL")
print(f"Using model: {model_name}")
print("Sending request to OpenRouter...")

# 2. Configure OpenAI client
client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL"), 
    api_key=os.environ.get("LLM_API_KEY")
)

# 3. Call the model
res = client.chat.completions.create(
    model=model_name,
    messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
)

# 4. Output the result
print(f"The model says: {res.choices[0].message.content}")