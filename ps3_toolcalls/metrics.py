"""
PS-3: Function-Calling Metric Definitions & Evaluator (Official Section 6.3 & 8.1 Schemas)
Validates tools:
1. capture_ptp
2. send_payment_link
3. mark_dispute
4. escalate_human
5. log_disposition (verbatim trailing space enum: "ESCALATED ")

Calculates:
- Correct-Tool Rate
- Argument-Level Accuracy
- Malformed-Argument Rate
- Spurious Call Rate (over-firing on ambiguous turns)
- Missed Call Rate (under-firing on clear turns, with log_disposition tracked)
- English-vs-Hinglish Delta
"""

import json
from typing import Dict, Any, List, Optional

VALID_DISPUTE_TYPES = ["not_mine", "already_paid", "amount_wrong", "other"]
VALID_ESCALATE_REASONS = ["borrower_request", "distress", "dispute", "abuse", "out_of_scope"]
VALID_CHANNELS = ["sms", "whatsapp"]
VALID_CONFIDENCE = ["firm", "tentative"]
# NOTE: "ESCALATED " has an intentional trailing space verbatim from Section 6.3 appendix!
VALID_DISPOSITION_CODES = ["PTP", "PAID", "REFUSED", "DISPUTE", "WRONG_NUMBER", "CALLBACK", "NO_CONTACT", "ESCALATED "]

def validate_arguments(tool_name: str, args: Dict[str, Any], expected_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates arguments against the official Section 6.3 schemas and expected ground truth.
    """
    is_malformed = False
    malformed_reasons = []
    args_match = True

    if tool_name == "capture_ptp":
        amt = args.get("promised_amount")
        if amt is None:
            is_malformed = True
            malformed_reasons.append("Missing required 'promised_amount'")
        elif not isinstance(amt, (int, float)):
            is_malformed = True
            malformed_reasons.append(f"'promised_amount' is not a number: {amt}")
        elif expected_args.get("promised_amount") is not None and float(amt) != float(expected_args["promised_amount"]):
            args_match = False

        dt = args.get("promised_date")
        if not dt or not isinstance(dt, str):
            is_malformed = True
            malformed_reasons.append("Missing or non-string 'promised_date'")
        elif expected_args.get("promised_date") and dt != expected_args["promised_date"]:
            args_match = False

        conf = args.get("confidence")
        if conf is not None:
            if conf not in VALID_CONFIDENCE:
                is_malformed = True
                malformed_reasons.append(f"Invalid confidence enum: {conf}")
            elif expected_args.get("confidence") and conf != expected_args["confidence"]:
                args_match = False

    elif tool_name == "send_payment_link":
        ch = args.get("channel")
        if ch not in VALID_CHANNELS:
            is_malformed = True
            malformed_reasons.append(f"Invalid channel enum: {ch}")
        elif expected_args.get("channel") and ch != expected_args["channel"]:
            args_match = False

        amt = args.get("amount")
        if amt is None or not isinstance(amt, (int, float)):
            is_malformed = True
            malformed_reasons.append(f"Missing or non-numeric 'amount': {amt}")
        elif expected_args.get("amount") is not None and float(amt) != float(expected_args["amount"]):
            args_match = False

    elif tool_name == "mark_dispute":
        dt = args.get("dispute_type")
        if dt not in VALID_DISPUTE_TYPES:
            is_malformed = True
            malformed_reasons.append(f"Invalid dispute_type: {dt}")
        elif expected_args.get("dispute_type") and dt != expected_args["dispute_type"]:
            args_match = False

    elif tool_name == "escalate_human":
        r = args.get("reason")
        if r not in VALID_ESCALATE_REASONS:
            is_malformed = True
            malformed_reasons.append(f"Invalid reason enum: {r}")
        elif expected_args.get("reason") and r != expected_args["reason"]:
            args_match = False

    elif tool_name == "log_disposition":
        c = args.get("code")
        if c not in VALID_DISPOSITION_CODES:
            is_malformed = True
            malformed_reasons.append(f"Invalid code enum: {c} (Must match official Section 6.3 enums including 'ESCALATED ')")
        elif expected_args.get("code") and c != expected_args["code"]:
            args_match = False

    else:
        is_malformed = True
        malformed_reasons.append(f"Unknown tool name: {tool_name}")
        args_match = False

    return {
        "is_malformed": is_malformed,
        "malformed_reasons": malformed_reasons,
        "arguments_match": args_match and not is_malformed
    }

def evaluate_case(
    predicted_call: Optional[Dict[str, Any]],
    expected_tool: Optional[str],
    expected_args: Dict[str, Any],
    is_ambiguous: bool = False
) -> Dict[str, Any]:
    """
    Evaluates a single prediction against ground truth.
    """
    pred_tool = None
    pred_args = {}

    if predicted_call:
        fn = predicted_call.get("function", predicted_call)
        pred_tool = fn.get("name")
        raw_args = fn.get("arguments", {})
        if isinstance(raw_args, str):
            try:
                pred_args = json.loads(raw_args)
            except Exception:
                pred_args = {}
        elif isinstance(raw_args, dict):
            pred_args = raw_args

    is_spurious = False
    is_missed = False
    is_correct_tool = False
    is_argument_accurate = False
    is_malformed = False
    malformed_details = []

    if expected_tool is None:
        # Ambiguous / soft statement where no tool should be triggered
        if pred_tool is not None:
            is_spurious = True
            is_correct_tool = False
        else:
            is_correct_tool = True
            is_argument_accurate = True
    else:
        if pred_tool is None:
            is_missed = True
            is_correct_tool = False
        elif pred_tool == expected_tool:
            is_correct_tool = True
            val = validate_arguments(pred_tool, pred_args, expected_args)
            is_malformed = val["is_malformed"]
            malformed_details = val["malformed_reasons"]
            is_argument_accurate = val["arguments_match"]
        else:
            is_correct_tool = False

    return {
        "pred_tool": pred_tool,
        "pred_args": pred_args,
        "expected_tool": expected_tool,
        "expected_args": expected_args,
        "is_correct_tool": is_correct_tool,
        "is_argument_accurate": is_argument_accurate,
        "is_malformed": is_malformed,
        "is_spurious": is_spurious,
        "is_missed": is_missed,
        "malformed_details": malformed_details
    }

def compute_suite_metrics(eval_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes aggregate metrics from a list of evaluated records.
    """
    total = len(eval_records)
    if total == 0:
        return {}

    correct_tool_count = sum(1 for r in eval_records if r["is_correct_tool"])
    arg_accurate_count = sum(1 for r in eval_records if r["is_argument_accurate"])
    malformed_count = sum(1 for r in eval_records if r["is_malformed"])
    spurious_count = sum(1 for r in eval_records if r["is_spurious"])
    missed_count = sum(1 for r in eval_records if r["is_missed"])

    ambiguous_total = sum(1 for r in eval_records if r.get("is_ambiguous", False))
    clear_total = total - ambiguous_total

    # Track missing log_disposition specifically per Section 8.1 design implication
    log_disp_total = sum(1 for r in eval_records if r.get("expected_tool") == "log_disposition")
    log_disp_missed = sum(1 for r in eval_records if r.get("expected_tool") == "log_disposition" and r["is_missed"])

    return {
        "total_cases": total,
        "clear_intent_cases": clear_total,
        "ambiguous_cases": ambiguous_total,
        "correct_tool_rate_pct": round(correct_tool_count / total * 100, 2),
        "argument_accuracy_rate_pct": round(arg_accurate_count / total * 100, 2),
        "malformed_argument_rate_pct": round(malformed_count / total * 100, 2),
        "spurious_call_rate_pct": round(spurious_count / ambiguous_total * 100, 2) if ambiguous_total > 0 else 0.0,
        "missed_call_rate_pct": round(missed_count / clear_total * 100, 2) if clear_total > 0 else 0.0,
        "log_disposition_missed_rate_pct": round(log_disp_missed / log_disp_total * 100, 2) if log_disp_total > 0 else 0.0
    }
