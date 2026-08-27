import json
import os
import requests

API_URL = "http://127.0.0.1:9000/triage"
EVAL_FILE = os.path.join("evals", "cases.json")

def run_evaluation():
    if not os.path.exists(EVAL_FILE):
        print(f"❌ Error: {EVAL_FILE} not found.")
        return

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"\n🧪 Running Evaluation on {len(cases)} Test Cases against {API_URL}...\n")
    passed = 0
    failed = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        expected_cat = case["expected_category"]
        
        try:
            response = requests.post(
                API_URL,
                json={"text": text},
                headers={"Content-Type": "application/json"},
                timeout=35.0
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_cat = data.get("category")
                
                if actual_cat == expected_cat:
                    print(f"  [Case {case_id}] ✅ PASS | Category: '{actual_cat}'")
                    passed += 1
                else:
                    print(f"  [Case {case_id}] ❌ FAIL | Expected: '{expected_cat}', Got: '{actual_cat}'")
                    failed.append((case_id, text, expected_cat, actual_cat))
            else:
                print(f"  [Case {case_id}] ❌ ERROR | HTTP Status {response.status_code}")
                failed.append((case_id, text, expected_cat, f"HTTP {response.status_code}"))
        except Exception as e:
            print(f"  [Case {case_id}] ❌ EXCEPTION | {str(e)}")
            failed.append((case_id, text, expected_cat, str(e)))

    accuracy = (passed / len(cases)) * 100
    print("\n" + "="*50)
    print(f"📊 EVALUATION SUMMARY SCORE: {passed}/{len(cases)} ({accuracy:.1f}%)")
    print("="*50)

    if failed:
        print("\nFailed Cases:")
        for fid, ftext, fexp, fgot in failed:
            print(f"  - Case {fid}: Expected '{fexp}', got '{fgot}' (Text: '{ftext}')")
    else:
        print("\n🎉 Perfect 100% Accuracy Score!")

if __name__ == "__main__":
    run_evaluation()