"""
Unified Model Client for Collections Evaluation
Supports Sarvam AI (Sarvam-105B), Groq (Qwen3.8-27B), and Google Gemini Flash.
Tracks latency, time-to-first-token approximations, status codes, and handles backoff.
"""

import os
import time
import json
import httpx
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

def load_env() -> Dict[str, str]:
    """Loads keys from .env in workspace root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

ENV = load_env()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or ENV.get("GROQ_API_KEY", "")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY") or ENV.get("SARVAM_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or ENV.get("GEMINI_API_KEY", "")

class ModelClient:
    def __init__(self):
        self.sarvam_key = SARVAM_API_KEY
        self.groq_key = GROQ_API_KEY
        self.gemini_key = GEMINI_API_KEY
        self.client = httpx.Client(timeout=30.0)

    def generate(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 256,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Standardized completion call across Sarvam, Groq, and Gemini.
        """
        start_time = time.perf_counter()
        try:
            if provider == "groq":
                return self._call_groq(model, messages, temperature, max_tokens, tools, response_format, start_time)
            elif provider == "sarvam":
                return self._call_sarvam(model, messages, temperature, max_tokens, tools, start_time)
            elif provider == "gemini":
                return self._call_gemini(model, messages, temperature, max_tokens, tools, start_time)
            elif provider == "ollama":
                return self._call_ollama(model, messages, temperature, max_tokens, tools, response_format, start_time)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "content": "",
                "tool_calls": None,
                "latency_ms": latency_ms,
                "provider": provider,
                "model": model,
                "status": "error",
                "error": str(e)
            }

    def _call_groq(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]],
        response_format: Optional[Dict[str, Any]],
        start_time: float
    ) -> Dict[str, Any]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"


        for attempt in range(3):
            try:
                resp = self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                data = resp.json()
                choice = data["choices"][0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                tool_calls = message.get("tool_calls")
                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "latency_ms": latency_ms,
                    "provider": "groq",
                    "model": model,
                    "status": "success",
                    "error": None
                }
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(1.5)

        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "content": "",
            "tool_calls": None,
            "latency_ms": latency_ms,
            "provider": "groq",
            "model": model,
            "status": "error",
            "error": "Exhausted retries on Groq API"
        }


    def _call_sarvam(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]],
        start_time: float
    ) -> Dict[str, Any]:
        url = "https://api.sarvam.ai/v1/chat/completions"
        headers = {
            "api-subscription-key": self.sarvam_key,
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        # If tools are requested, inject tool definitions into system message for Sarvam
        if tools:
            tool_prompt = (
                "\nYou have access to the following functions. If an action is required, output your response as valid JSON matching this schema: "
                f"{{'name': '<function_name>', 'arguments': {{...}}}}.\nTools: "
                + json.dumps(tools)
            )
            # clone messages
            adapted_messages = []
            for m in messages:
                if m["role"] == "system":
                    adapted_messages.append({"role": "system", "content": m["content"] + tool_prompt})
                else:
                    adapted_messages.append(m)
            payload["messages"] = adapted_messages

        for attempt in range(3):
            try:
                resp = self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                data = resp.json()
                content = data["choices"][0]["message"].get("content") or ""
                
                # Check for structured tool call in content
                tool_calls = None
                if tools:
                    # attempt to parse JSON from content
                    try:
                        clean_c = content.strip()
                        if clean_c.startswith("```json"):
                            clean_c = clean_c[7:].rstrip("`").strip()
                        elif clean_c.startswith("```"):
                            clean_c = clean_c[3:].rstrip("`").strip()
                        parsed = json.loads(clean_c)
                        if isinstance(parsed, dict) and "name" in parsed:
                            tool_calls = [{
                                "id": "call_sarvam_1",
                                "type": "function",
                                "function": {
                                    "name": parsed.get("name"),
                                    "arguments": json.dumps(parsed.get("arguments", {}))
                                }
                            }]
                    except Exception:
                        pass

                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "latency_ms": latency_ms,
                    "provider": "sarvam",
                    "model": model,
                    "status": "success",
                    "error": None
                }
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(1.5)

        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "content": "",
            "tool_calls": None,
            "latency_ms": latency_ms,
            "provider": "sarvam",
            "model": model,
            "status": "error",
            "error": "Exhausted retries on Sarvam API"
        }


    def _call_gemini(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]],
        start_time: float
    ) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.gemini_key
        }

        # Convert messages to Gemini format
        contents = []
        system_instruction = None
        for m in messages:
            if m["role"] == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
            elif m["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": m["content"]}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if tools:
            # Format function declarations for Gemini
            function_declarations = []
            for t in tools:
                fn = t.get("function", t)
                function_declarations.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {})
                })
            payload["tools"] = [{"functionDeclarations": function_declarations}]

        for attempt in range(3):
            try:
                resp = self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                data = resp.json()
                candidate = data.get("candidates", [{}])[0]
                content_part = candidate.get("content", {}).get("parts", [{}])[0]
                
                content = content_part.get("text", "")
                tool_calls = None
                if "functionCall" in content_part:
                    fc = content_part["functionCall"]
                    tool_calls = [{
                        "id": "call_gemini_1",
                        "type": "function",
                        "function": {
                            "name": fc.get("name"),
                            "arguments": json.dumps(fc.get("args", {}))
                        }
                    }]

                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "latency_ms": latency_ms,
                    "provider": "gemini",
                    "model": model,
                    "status": "success",
                    "error": None
                }
            except Exception as e:

                if attempt == 2:
                    raise e
                time.sleep(2.0 * (attempt + 1))
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "content": "",
            "tool_calls": None,
            "latency_ms": latency_ms,
            "provider": "gemini",
            "model": model,
            "status": "error",
            "error": "Exhausted retries on Gemini API"
        }

    def _call_ollama(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]],
        response_format: Optional[Dict[str, Any]],
        start_time: float
    ) -> Dict[str, Any]:
        """
        Calls local Ollama instance via OpenAI-compatible endpoint (/v1/chat/completions).
        Default host: http://127.0.0.1:11434 (configurable via OLLAMA_HOST).
        """
        ollama_host = os.environ.get("OLLAMA_HOST") or ENV.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        if not ollama_host.startswith("http"):
            ollama_host = f"http://{ollama_host}"
        ollama_host = ollama_host.replace("0.0.0.0", "127.0.0.1")
        url = f"{ollama_host.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(3):
            try:
                resp = self.client.post(url, headers=headers, json=payload, timeout=60.0)
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                data = resp.json()
                choice = data["choices"][0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                tool_calls = message.get("tool_calls")
                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "latency_ms": latency_ms,
                    "provider": "ollama",
                    "model": model,
                    "status": "success",
                    "error": None
                }
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(1.0)

        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "content": "",
            "tool_calls": None,
            "latency_ms": latency_ms,
            "provider": "ollama",
            "model": model,
            "status": "error",
            "error": "Exhausted retries on local Ollama service"
        }


client_singleton = ModelClient()

def get_client() -> ModelClient:
    return client_singleton

