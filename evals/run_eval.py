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
        expected_urg = case.get("expected_urgency")
        
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
                actual_urg = data.get("urgency")
                
                cat_match = actual_cat == expected_cat
                urg_match = (expected_urg is None) or (actual_urg == expected_urg)
                
                if cat_match and urg_match:
                    print(f"  [Case {case_id}] ✅ PASS | Category: '{actual_cat}', Urgency: '{actual_urg}'")
                    passed += 1
                elif not cat_match:
                    print(f"  [Case {case_id}] ❌ FAIL | Category: expected '{expected_cat}', got '{actual_cat}'")
                    failed.append((case_id, text, expected_cat, actual_cat))
                else:
                    print(f"  [Case {case_id}] ❌ FAIL | Urgency: expected '{expected_urg}', got '{actual_urg}'")
                    failed.append((case_id, text, f"urgency={expected_urg}", f"urgency={actual_urg}"))
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