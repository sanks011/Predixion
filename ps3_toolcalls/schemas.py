"""
PS-3: Official Function Schemas (Section 6.3 - FIXED, do not modify)
Open-Weight Collections Agent Challenge

Organizers' constraint:
The schemas are fixed and given.
Note: log_disposition.code includes "ESCALATED " with a trailing space verbatim from the official appendix.
"""

from typing import List, Dict, Any

# Official 5 schemas from Section 6.3 formatted as OpenAI-compatible tools
OFFICIAL_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "capture_ptp",
            "description": "Record a promise to pay made by the borrower.",
            "parameters": {
                "type": "object",
                "properties": {
                    "promised_amount": {
                        "type": "number",
                        "description": "Amount the borrower promised to pay."
                    },
                    "promised_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Date by which borrower promises to pay (YYYY-MM-DD)."
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["firm", "tentative"],
                        "description": "Confidence level of commitment."
                    }
                },
                "required": ["promised_amount", "promised_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_payment_link",
            "description": "Send a payment link over SMS or WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["sms", "whatsapp"],
                        "description": "Communication channel for payment link."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Monetary amount for the payment link."
                    }
                },
                "required": ["channel", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mark_dispute",
            "description": "Borrower disputes the debt. Halts recovery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dispute_type": {
                        "type": "string",
                        "enum": ["not_mine", "already_paid", "amount_wrong", "other"],
                        "description": "Nature of the dispute asserted by borrower."
                    },
                    "borrower_statement": {
                        "type": "string",
                        "description": "Summary statement of dispute provided by borrower."
                    }
                },
                "required": ["dispute_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_human",
            "description": "Transfer to a human agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": ["borrower_request", "distress", "dispute", "abuse", "out_of_scope"],
                        "description": "Reason triggering human transfer."
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_disposition",
            "description": "Record the outcome of the call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        # NOTE: "ESCALATED " has an intentional trailing space verbatim from Section 6.3 appendix!
                        "enum": ["PTP", "PAID", "REFUSED", "DISPUTE", "WRONG_NUMBER", "CALLBACK", "NO_CONTACT", "ESCALATED "],
                        "description": "Outcome code for the call."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Call disposition notes or context."
                    }
                },
                "required": ["code"]
            }
        }
    }
]

def get_tools() -> List[Dict[str, Any]]:
    """Returns the official 5 tools."""
    return OFFICIAL_TOOL_SCHEMAS
