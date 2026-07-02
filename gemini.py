"""Gemini API client — plain REST via urllib, no SDK needed.

Returns parsed JSON from the model. Handles model fallback and rate-limit retries.
"""
import json
import os
import time
import urllib.request
import urllib.error

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# First model that works wins; env var GEMINI_MODEL overrides the list.
MODEL_CANDIDATES = [
    os.environ.get("GEMINI_MODEL", ""),
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

_working_model = None


def _api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Put it in the .env file (see .env.example)."
        )
    return key


def _call_model(model, system_prompt, user_prompt):
    url = f"{API_BASE}/{model}:generateContent?key={_api_key()}"
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ask_json(system_prompt, user_prompt, max_retries=3):
    """Ask Gemini and return the response parsed as JSON (dict or list)."""
    global _working_model
    # Prefer the model that last worked, but ALWAYS keep the others as fallback —
    # free-tier models regularly return 503 "high demand" and we switch instead of dying.
    models = [m for m in MODEL_CANDIDATES if m]
    if _working_model and _working_model in models:
        models.remove(_working_model)
    if _working_model:
        models.insert(0, _working_model)
    last_error = None

    for sweep in range(2):  # if every model is busy, wait once and sweep again
        if sweep > 0:
            time.sleep(20)
        for model in models:
            for attempt in range(max_retries):
                try:
                    data = _call_model(model, system_prompt, user_prompt)
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    _working_model = model
                    return _parse_json(text)
                except urllib.error.HTTPError as e:
                    detail = e.read().decode("utf-8", errors="ignore")[:500]
                    last_error = f"HTTP {e.code} from {model}: {detail}"
                    if e.code in (404, 503):
                        break  # model missing or overloaded — switch to the next model
                    if e.code in (429, 500):
                        time.sleep(5 * (attempt + 1))  # rate limit / hiccup — wait and retry
                        continue
                    raise RuntimeError(last_error)
                except (KeyError, IndexError):
                    last_error = f"{model} returned an unexpected/empty response"
                    time.sleep(2)
                    continue

    raise RuntimeError(f"Gemini call failed after retries. Last error: {last_error}")


def _parse_json(text):
    """Model output should be pure JSON, but strip code fences just in case."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
