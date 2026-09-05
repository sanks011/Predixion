"""
PS-1: The Guardrail Gauntlet Evaluation Runner
Executes the adversarial attack suite across evaluated models, scores responses using the automated compliance judge,
and generates granular metrics with English-vs-Indic safety deltas.
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
from harness.system_prompt import get_system_prompt
from ps1_guardrail.scorer import get_scorer
from ps1_guardrail.human_validation import evaluate_judge_on_validation_subset

MODELS_TO_EVALUATE = [
    {"id": "sarvam-105b-conversations", "provider": "sarvam", "name": "Sarvam-105B (Indic Native)"},
    {"id": "qwen/qwen3.8-27b", "provider": "groq", "name": "Qwen3.8-27B (Groq Open-Weight)"},
    {"id": "gemini-2.5-flash", "provider": "gemini", "name": "Gemini Flash (Hosted Baseline)"}
]

def load_attacks(sample_limit: int = 0) -> List[Dict[str, Any]]:
    path = Path(__file__).resolve().parent / "attacks.jsonl"
    attacks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                attacks.append(json.loads(line))
    if sample_limit > 0:
        return attacks[:sample_limit]
    return attacks

def run_ps1_evaluation(sample_limit: int = 0, delay_sec: float = 1.0) -> Dict[str, Any]:
    client = get_client()
    scorer = get_scorer()
    attacks = load_attacks(sample_limit)
    print(f"Loaded {len(attacks)} attacks for PS-1 Guardrail Gauntlet evaluation.")

    results_by_model: Dict[str, Any] = {}

    for m_info in MODELS_TO_EVALUATE:
        m_id = m_info["id"]
        provider = m_info["provider"]
        m_name = m_info["name"]
        print(f"\n==========================================")
        print(f"Evaluating {m_name} ({m_id})...")
        print(f"==========================================")

        records = []
        violations_count = 0
        total_latency = 0.0

        lang_stats: Dict[str, Dict[str, int]] = {
            "en": {"total": 0, "violations": 0},
            "hi": {"total": 0, "violations": 0},
            "hinglish": {"total": 0, "violations": 0},
            "mr": {"total": 0, "violations": 0}
        }

        category_stats: Dict[str, Dict[str, int]] = {}

        for idx, item in enumerate(attacks):
            turn_type = item.get("turn_type", "single_turn")
            category = item["category"]
            lang = item["language"]
            bucket = item.get("delinquency_bucket", "30-DPD")

            if category not in category_stats:
                category_stats[category] = {"total": 0, "violations": 0}

            system_prompt = get_system_prompt(bucket)

            if turn_type == "single_turn":
                user_msg = item["borrower_turn"]
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ]
                call_res = client.generate(
                    provider=provider,
                    model=m_id,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=200
                )
                agent_reply = call_res.get("content", "")
                latency_ms = call_res.get("latency_ms", 0.0)
                eval_turn_borrower = user_msg

            else:
                # Multi-turn Crescendo escalation
                messages = [{"role": "system", "content": system_prompt}]
                agent_reply = ""
                latency_ms = 0.0
                eval_turn_borrower = ""
                for turn_text in item.get("borrower_turns", []):
                    messages.append({"role": "user", "content": turn_text})
                    sub_res = client.generate(
                        provider=provider,
                        model=m_id,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=200
                    )
                    agent_reply = sub_res.get("content", "")
                    latency_ms += sub_res.get("latency_ms", 0.0)
                    messages.append({"role": "assistant", "content": agent_reply})
                    eval_turn_borrower = turn_text # evaluate final escalated turn

            total_latency += latency_ms

            vcode = item.get("v_code", "V1")
            # Score response with LLM Judge
            score = scorer.score_turn(
                borrower_turn=eval_turn_borrower,
                agent_turn=agent_reply,
                target_vcode=vcode
            )

            is_violation = score.get("violated", score.get("violation_detected", False))
            if vcode not in category_stats:
                category_stats[vcode] = {"total": 0, "violations": 0}

            if is_violation:
                violations_count += 1
                lang_stats[lang]["violations"] += 1
                category_stats[vcode]["violations"] += 1

            lang_stats[lang]["total"] += 1
            category_stats[vcode]["total"] += 1

            records.append({
                "case_id": item["id"],
                "v_code": vcode,
                "category": category,
                "language": lang,
                "turn_type": turn_type,
                "borrower_turn": eval_turn_borrower,
                "agent_reply": agent_reply,
                "latency_ms": round(latency_ms, 2),
                "judge_score": score
            })

            print(f"[{idx+1}/{len(attacks)}] {m_id} | {lang} | {vcode} ({category}) -> Violation: {is_violation} ({latency_ms:.0f}ms)")
            if delay_sec > 0:
                time.sleep(delay_sec)

        # Compute aggregates
        total_cases = len(attacks)
        overall_violation_rate = (violations_count / total_cases * 100) if total_cases > 0 else 0.0

        en_total = lang_stats["en"]["total"]
        en_violation_rate = (lang_stats["en"]["violations"] / en_total * 100) if en_total > 0 else 0.0

        indic_total = lang_stats["hi"]["total"] + lang_stats["hinglish"]["total"] + lang_stats["mr"]["total"]
        indic_violations = lang_stats["hi"]["violations"] + lang_stats["hinglish"]["violations"] + lang_stats["mr"]["violations"]
        indic_violation_rate = (indic_violations / indic_total * 100) if indic_total > 0 else 0.0

        english_vs_indic_delta = indic_violation_rate - en_violation_rate

        results_by_model[m_id] = {
            "model_name": m_name,
            "provider": provider,
            "total_cases": total_cases,
            "violations_detected": violations_count,
            "overall_violation_rate_pct": round(overall_violation_rate, 2),
            "avg_latency_ms": round(total_latency / total_cases, 2) if total_cases > 0 else 0.0,
            "english_violation_rate_pct": round(en_violation_rate, 2),
            "indic_violation_rate_pct": round(indic_violation_rate, 2),
            "english_vs_indic_safety_delta": round(english_vs_indic_delta, 2),
            "language_breakdown": lang_stats,
            "vcode_breakdown": {
                c: {
                    "total": v["total"],
                    "violations": v["violations"],
                    "rate_pct": round((v["violations"] / v["total"] * 100), 2) if v["total"] > 0 else 0.0
                }
                for c, v in sorted(category_stats.items())
            },
            "cases": records
        }

    # Run human rater validation on benchmark subset
    print("\nValidating Automated Judge against Hand-Labeled Subset...")
    validation_metrics = evaluate_judge_on_validation_subset(scorer)

    final_payload = {
        "benchmark": "PS-1: The Guardrail Gauntlet",
        "taxonomy_grounding": "RBI RBC Directions 2026 & NBFC Section L",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": results_by_model,
        "judge_validation": validation_metrics
    }

    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "ps1_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, ensure_ascii=False)
    print(f"\nPS-1 Results successfully saved to {out_file}")
    return final_payload

if __name__ == "__main__":
    # Test run with first 12 cases or full run
    limit = 0
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    run_ps1_evaluation(sample_limit=limit)
