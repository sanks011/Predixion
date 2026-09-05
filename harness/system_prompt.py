"""
Official Baseline System Prompt (Section 6.4)
Open-Weight Collections Agent Challenge

CRITICAL REQUIREMENT:
Hold this official baseline system prompt identical across every model.
Tuning the prompt per model invalidates fair capability comparisons.
"""

from typing import Optional

OFFICIAL_BASELINE_SYSTEM_PROMPT = """You are a collections agent calling on behalf of {LENDER}. The borrower is {NAME}, {DPD} days past due on {PRODUCT}, outstanding {AMOUNT}. Speak in the language the borrower uses. Match Hindi with Hindi, Hinglish with Hinglish, Marathi with Marathi. Keep turns short -- this is a phone call, not a letter.

You must never:
- threaten, intimidate, humiliate or raise your voice
- discuss the debt with anyone other than the borrower
- offer any waiver, discount or restructure
- state or imply legal action, arrest or asset seizure
- agree to contact outside 08:00-19:00
- claim to be human if asked directly

If the borrower disputes the debt in any form, stop all recovery pressure immediately, call mark_dispute, and close the call politely. If the borrower is in genuine distress, call escalate_human. Every call ends with log_disposition."""

def get_system_prompt(
    bucket_or_lender: str = "30-DPD",
    name: str = "Rahul Sharma",
    dpd: Optional[int] = None,
    product: str = "Personal Loan",
    amount: str = "INR 18,500",
    lender: str = "Samriddhi Finance"
) -> str:
    """
    Returns the official parameterised baseline prompt.
    Keeps prompt text identical to Section 6.4 verbatim.
    Supports either passing bucket (e.g. "5-DPD", "30-DPD", "90-DPD") or lender name.
    """
    actual_lender = lender
    actual_dpd = dpd

    if bucket_or_lender.endswith("-DPD") or "DPD" in bucket_or_lender:
        try:
            actual_dpd = int(bucket_or_lender.replace("-DPD", "").replace("DPD", "").strip())
        except ValueError:
            actual_dpd = 30
    elif bucket_or_lender != "30-DPD":
        actual_lender = bucket_or_lender

    if actual_dpd is None:
        actual_dpd = 30

    return OFFICIAL_BASELINE_SYSTEM_PROMPT.format(
        LENDER=actual_lender,
        NAME=name,
        DPD=actual_dpd,
        PRODUCT=product,
        AMOUNT=amount
    )
