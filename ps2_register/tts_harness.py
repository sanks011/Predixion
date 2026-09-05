"""
PS-2: Text-to-Speech (TTS) Round-Trip Harness
Integrates with Sarvam Bulbul v3 speech synthesis.
Carries model responses into audio, evaluates script readiness, and stores audio evidence.
"""

import base64
import json
import re
import sys
import httpx
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from harness.model_client import SARVAM_API_KEY

AUDIO_OUTPUT_DIR = Path(__file__).resolve().parent / "audio_samples"
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class TTSHarness:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SARVAM_API_KEY
        self.url = "https://api.sarvam.ai/text-to-speech"
        self.client = httpx.Client(timeout=30.0)

    def analyze_script_readiness(self, text: str) -> Dict[str, Any]:
        """
        Analyzes script consistency, currency symbol usage, and numeral formatting.
        Returns a score (1-5) and specific failure mode tags.
        """
        issues = []
        # Check for Devanagari vs Latin characters
        has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))
        has_latin = bool(re.search(r'[a-zA-Z]', text))
        
        script_type = "mixed" if (has_devanagari and has_latin) else ("devanagari" if has_devanagari else "roman_hinglish")
        
        # Check for mid-sentence script toggling
        if has_devanagari and has_latin:
            issues.append("mixed_script_glitch")

        # Check for raw currency symbols (₹, $, Rs., INR)
        if re.search(r'[₹$]|(Rs\.?)|(INR)', text):
            issues.append("raw_currency_symbol")

        # Check for raw numerals (e.g. 15000 vs written out words)
        if re.search(r'\b\d{3,}\b', text):
            issues.append("raw_unexpanded_numeral")

        # Check for forbidden punctuation or symbols (/, @, #, etc.)
        if re.search(r'[/\\_~^<>]', text):
            issues.append("extraneous_symbols")

        # Compute readiness score (1 to 5)
        if not issues:
            score = 5
        elif len(issues) == 1 and issues[0] == "raw_unexpanded_numeral":
            score = 4
        elif "mixed_script_glitch" in issues and "raw_currency_symbol" in issues:
            score = 2
        elif len(issues) >= 3:
            score = 1
        else:
            score = 3

        return {
            "score": score,
            "script_type": script_type,
            "has_devanagari": has_devanagari,
            "has_latin": has_latin,
            "issues": issues,
            "is_clean": len(issues) == 0
        }

    def synthesize_speech(
        self,
        text: str,
        filename_stem: str,
        target_lang: str = "hi-IN",
        speaker: str = "aditya",
        model: str = "bulbul:v3"
    ) -> Dict[str, Any]:
        """
        Synthesizes speech using Sarvam Bulbul v3 and persists the audio WAV file.
        """
        script_analysis = self.analyze_script_readiness(text)
        clean_text = text.strip()
        if not clean_text:
            return {"status": "error", "error": "Empty text provided", "script_analysis": script_analysis}

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [clean_text],
            "target_language_code": target_lang,
            "speaker": speaker,
            "model": model,
            "pace": 1.0,
            "speech_sample_rate": 16000
        }

        try:
            resp = self.client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            audios = data.get("audios", [])
            if not audios:
                return {"status": "error", "error": "No audio returned", "script_analysis": script_analysis}

            audio_b64 = audios[0]
            audio_bytes = base64.b64decode(audio_b64)
            audio_path = AUDIO_OUTPUT_DIR / f"{filename_stem}.wav"
            with open(audio_path, "wb") as af:
                af.write(audio_bytes)

            file_size_kb = round(len(audio_bytes) / 1024, 2)
            return {
                "status": "success",
                "audio_path": str(audio_path),
                "filename": audio_path.name,
                "file_size_kb": file_size_kb,
                "script_analysis": script_analysis
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "script_analysis": script_analysis
            }

tts_singleton = TTSHarness()

def get_tts_harness() -> TTSHarness:
    return tts_singleton
