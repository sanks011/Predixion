"""
PS-3: Function-Calling Evaluation Runner
Executes the 200-case suite against Sarvam, Groq Qwen, and Gemini Flash.
Calculates English vs Hinglish deltas, argument accuracy, and compiles the Error Taxonomy.
"""

import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from harness.model_client import get_client
from ps3_toolcalls.schemas import get_tools
from ps3_toolcalls.metrics import evaluate_case, compute_suite_metrics

MODELS = [
    {"id": "sarvam-105b-conversations", "provider": "sarvam", "name": "Sarvam-105B (Indic Native)"},
    {"id": "qwen/qwen3.8-27b", "provider": "groq", "name": "Qwen3.8-27B (Groq Open-Weight)"},
    {"id": "gemini-2.5-flash", "provider": "gemini", "name": "Gemini Flash (Hosted Baseline)"}
]

TOOL_SYSTEM_PROMPT = """You are an intelligent banking collections system backend.
Your job is to analyze the borrower's statement and call the appropriate tool with accurately extracted arguments.
- If the borrower commits to paying an amount on a date, call `capture_ptp`.
- If the borrower requests a payment link over SMS or WhatsApp, call `send_payment_link`.
- If the borrower disputes the debt, claims fraud, already paid, or incorrect amount, call `mark_dispute`.
- If the borrower requests human transfer, is in distress, or is abusive, call `escalate_human`.
- If the statement concludes a call outcome (refusal, payment, callback request), call `log_disposition`.
- If the borrower's statement is ambiguous, non-committal ('shayad', 'maybe', 'dekhta hoon', 'pata nahi'), DO NOT CALL ANY TOOL. Respond with a clarifying message instead.
"""

def load_suite(sample_limit: int = 0) -> List[Dict[str, Any]]:
    path = Path(__file__).resolve().parent / "test_suite.jsonl"
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    if sample_limit > 0:
        return cases[:sample_limit]
    return cases

def run_ps3_evaluation(sample_limit: int = 0, delay_sec: float = 0.8) -> Dict[str, Any]:
    client = get_client()
    tools = get_tools()
    cases = load_suite(sample_limit)
    print(f"Loaded {len(cases)} cases for PS-3 Tool Calling evaluation.")

    results_by_model: Dict[str, Any] = {}

    for m_info in MODELS:
        m_id = m_info["id"]
        provider = m_info["provider"]
        m_name = m_info["name"]
        print(f"\n==========================================")
        print(f"PS-3 Evaluating {m_name} ({m_id})...")
        print(f"==========================================")

        en_evals = []
        hinglish_evals = []
        all_evals = []
        error_taxonomy_counts: Dict[str, int] = {
            "date_format_drift": 0,
            "amount_type_mismatch": 0,
            "spurious_ptp_on_hesitant_intent": 0,
            "missed_dispute_escalation": 0,
            "other_malformed": 0
        }

        for idx, item in enumerate(cases):
            lang = item["language"]
            utterance = item["utterance"]
            expected_tool = item["expected_tool"]
            expected_args = item["expected_args"]
            is_ambiguous = item["is_ambiguous"]

            messages = [
                {"role": "system", "content": TOOL_SYSTEM_PROMPT},
                {"role": "user", "content": utterance}
            ]

            call_res = client.generate(
                provider=provider,
                model=m_id,
                messages=messages,
                temperature=0.0,
                max_tokens=256,
                tools=tools
            )

            tool_calls = call_res.get("tool_calls")
            predicted_call = tool_calls[0] if tool_calls else None

            eval_res = evaluate_case(
                predicted_call=predicted_call,
                expected_tool=expected_tool,
                expected_args=expected_args,
                is_ambiguous=is_ambiguous
            )
            eval_res["case_id"] = item["id"]
            eval_res["language"] = lang
            eval_res["utterance"] = utterance

            # Error Taxonomy Categorization
            if eval_res["is_spurious"] and is_ambiguous:
                error_taxonomy_counts["spurious_ptp_on_hesitant_intent"] += 1
            elif eval_res["is_missed"] and expected_tool == "escalate_dispute":
                error_taxonomy_counts["missed_dispute_escalation"] += 1
            elif eval_res["is_malformed"]:
                details_str = " ".join(eval_res["malformed_details"])
                if "date" in details_str:
                    error_taxonomy_counts["date_format_drift"] += 1
                elif "amount" in details_str:
                    error_taxonomy_counts["amount_type_mismatch"] += 1
                else:
                    error_taxonomy_counts["other_malformed"] += 1

            if lang == "en":
                en_evals.append(eval_res)
            else:
                hinglish_evals.append(eval_res)
            all_evals.append(eval_res)

            print(f"[{idx+1}/{len(cases)}] {m_id} | {lang} | Exp: {expected_tool} | Pred: {eval_res['pred_tool']} | Tool Correct: {eval_res['is_correct_tool']}")
            if delay_sec > 0:
                time.sleep(delay_sec)

        en_metrics = compute_suite_metrics(en_evals)
        hinglish_metrics = compute_suite_metrics(hinglish_evals)
        total_metrics = compute_suite_metrics(all_evals)

        # Headline English-vs-Hinglish Delta
        tool_delta = round(en_metrics.get("correct_tool_rate_pct", 0) - hinglish_metrics.get("correct_tool_rate_pct", 0), 2)
        arg_delta = round(en_metrics.get("argument_accuracy_rate_pct", 0) - hinglish_metrics.get("argument_accuracy_rate_pct", 0), 2)

        results_by_model[m_id] = {
            "model_name": m_name,
            "provider": provider,
            "overall_metrics": total_metrics,
            "english_metrics": en_metrics,
            "hinglish_metrics": hinglish_metrics,
            "headline_deltas": {
                "english_vs_hinglish_tool_delta_pct": tool_delta,
                "english_vs_hinglish_argument_accuracy_delta_pct": arg_delta
            },
            "error_taxonomy": error_taxonomy_counts,
            "cases": all_evals
        }

    final_payload = {
        "benchmark": "PS-3: Tool Calls Under Code-Mixing",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": results_by_model,
        "error_taxonomy_definitions": {
            "date_format_drift": "Model outputs relative dates ('kal', 'next week') or verbal dates instead of ISO 8601 YYYY-MM-DD format.",
            "amount_type_mismatch": "Model outputs amounts as strings with currency symbols ('₹5,000') or text ('five thousand') instead of raw numbers.",
            "spurious_ptp_on_hesitant_intent": "Model over-fires capture_ptp when borrower uses non-committal discourse markers ('shayad kal dekhunga').",
            "missed_dispute_escalation": "Model fails to invoke escalate_dispute when borrower asserts identity theft or cybercrime using vernacular slang."
        }
    }

    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "ps3_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, ensure_ascii=False)
    print(f"\nPS-3 Results successfully saved to {out_file}")
    return final_payload

if __name__ == "__main__":
    limit = 0
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    run_ps3_evaluation(sample_limit=limit)
