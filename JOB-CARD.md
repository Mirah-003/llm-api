# Job card

What it does (one sentence): Classifies a customer support message so it lands on the right team's dashboard.

Input: { "text": "string, 1-2000 characters" }

Output: 
{ 
  "category": one of [billing|bug|feature|other],
  "urgency": one of [low|normal|high],
  "confidence": 0.0-1.0,
  "reason": "one short sentence explaining why" 
}

It must never: 
- invent a category outside the list 
- return free text outside the JSON
- give medical, legal or financial advice 

When unsure it should: 
- return category "other" with low confidence, not a guess