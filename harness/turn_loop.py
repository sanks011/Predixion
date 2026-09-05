"""
Multi-turn Conversation Driver
Manages conversation history, system prompt insertion, and response generation across turns.
"""

from typing import List, Dict, Any, Optional
from harness.model_client import ModelClient, get_client
from harness.system_prompt import get_system_prompt

class TurnLoop:
    def __init__(self, provider: str, model: str, bucket: str = "30-DPD", client: Optional[ModelClient] = None):
        self.provider = provider
        self.model = model
        self.bucket = bucket
        self.client = client or get_client()
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": get_system_prompt(bucket)}
        ]

    def add_user_turn(self, utterance: str) -> Dict[str, Any]:
        """Adds borrower utterance, calls model, records agent turn in history."""
        self.history.append({"role": "user", "content": utterance})
        result = self.client.generate(
            provider=self.provider,
            model=self.model,
            messages=self.history,
            temperature=0.2,
            max_tokens=256
        )
        if result["status"] == "success" and result["content"]:
            self.history.append({"role": "assistant", "content": result["content"]})
        return result

    def get_transcript(self) -> List[Dict[str, str]]:
        return self.history[1:] # Exclude system prompt
