# LLM Triage API

An API endpoint that classifies customer support messages into structured JSON decisions.

## Quickstart & Testing

### 1. Valid Request (Expect HTTP 200)
```bash
curl -X POST "http://127.0.0.1:8000/triage" \
     -H "Content-Type: application/json" \
     -d '{"text": "I was double charged on my invoice yesterday!"}'