# LLM Triage API

A lightweight API endpoint that classifies customer support messages into structured JSON decisions using an LLM backend.

## Quickstart & Testing

### 1. Valid Request (Expect HTTP 200)
```bash
curl -X POST "http://127.0.0.1:9000/triage" \
     -H "Content-Type: application/json" \
     -d '{"text": "I was double charged on my invoice yesterday!"}'
```

### 2. Deliberately Broken Request (Expect HTTP 400)
```bash
curl -X POST "http://127.0.0.1:9000/triage" \
     -H "Content-Type: application/json" \
     -d '{"text": ""}'
```
## Production Architecture & Reliability

- **Timeout:** Explicit 30.0-second timeout on the OpenAI client (`timeout=30.0`). Returns HTTP 504 on timeout.
- **Retry Policy:** Custom exponential backoff retry handler (`max_retries=0` on client, custom logic handles 1s, 2s, 4s backoff with jitter). Retries strictly on HTTP `429` rate limits and `5xx` server errors.
- **Fail-Fast:** Fails fast immediately on HTTP `401` (Unauthorized) or `400` errors without retrying.
- **Kill Switch:** Setting `LLM_ENABLED=false` in `.env` instantly disables AI calls and returns a deterministic fallback response.
- **Cost Observability:** Every request logs model, prompt version, input/output tokens, duration (ms), and repair status to `logs/cost.jsonl`.