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