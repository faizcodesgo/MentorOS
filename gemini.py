"""Gemini API client — plain REST via urllib, no SDK needed.

Returns parsed JSON from the model. Handles model fallback and rate-limit retries.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# First model that works wins; env var GEMINI_MODEL overrides the list.
# Note: gemini-2.0-flash has NO free-tier quota anymore (limit: 0) — don't use it.
MODEL_CANDIDATES = [
    os.environ.get("GEMINI_MODEL", ""),
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

_working_model = None

# How many tokens the model may spend "thinking" before it answers.
# 0 = off. Our prompts specify the output shape in detail, so a large thinking
# budget mostly buys latency. Tunable without a deploy via GEMINI_THINKING.
THINKING_BUDGET = int(os.environ.get("GEMINI_THINKING", "0"))

# Flipped off for the process if a model rejects thinkingConfig, so one
# unsupported field can never break every AI call in the app.
_thinking_ok = True


def _disable_thinking():
    global _thinking_ok
    _thinking_ok = False


def _api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Put it in the .env file (see .env.example)."
        )
    return key


def _call_model(model, system_prompt, user_prompt, thinking=True):
    url = f"{API_BASE}/{model}:generateContent?key={_api_key()}"
    gen = {
        "temperature": 0.4,
        "maxOutputTokens": 16384,
        "responseMimeType": "application/json",
    }
    # 2.5-flash runs "dynamic thinking" by default: it silently spends extra
    # output tokens reasoning before answering, paid for in wall-clock. Our
    # prompts specify the output shape in detail, so that budget buys little.
    # Capping it is the biggest latency win available. `thinking=False` is the
    # self-heal path for any model that rejects the field outright.
    if thinking and _thinking_ok:
        gen["thinkingConfig"] = {"thinkingBudget": THINKING_BUDGET}
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": gen,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # A model that doesn't know thinkingConfig 400s on every call. Rather
        # than let a speed optimisation take the whole app down, drop the field
        # permanently for this process and retry once.
        if e.code == 400 and thinking and _thinking_ok:
            _disable_thinking()
            return _call_model(model, system_prompt, user_prompt, thinking=False)
        raise


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
                    parsed = _parse_json(text)
                    _working_model = model
                    return parsed
                except json.JSONDecodeError as e:
                    # Model returned malformed JSON — regenerate (it's non-deterministic,
                    # a retry almost always yields valid JSON).
                    last_error = f"{model} returned invalid JSON: {e}"
                    time.sleep(2)
                    continue
                except urllib.error.HTTPError as e:
                    detail = e.read().decode("utf-8", errors="ignore")[:500]
                    last_error = f"HTTP {e.code} from {model}: {detail}"
                    if e.code in (404, 503):
                        break  # model missing or overloaded — switch to the next model
                    if e.code == 429 and "limit: 0" in detail:
                        break  # this model has NO free quota at all — switch models
                    if e.code in (429, 500):
                        time.sleep(5 * (attempt + 1))  # rate limit / hiccup — wait and retry
                        continue
                    raise RuntimeError(last_error)
                except (KeyError, IndexError):
                    last_error = f"{model} returned an unexpected/empty response"
                    time.sleep(2)
                    continue

    raise RuntimeError(f"Gemini call failed after retries. Last error: {last_error}")


def _call_grounded(model, system_prompt, user_prompt):
    """One grounded call — Google Search tool ON, NO responseMimeType (the two are
    mutually exclusive: 'Tool use with a response mime type application/json is
    unsupported', probed 28 Jul). Returns the model's PROSE, which is where the
    real source URLs live; groundingChunks carries expiring redirect URLs and is
    only a fallback, so we don't touch it here. maxOutputTokens is generous on
    purpose — a truncated answer loses both the URL and the citations."""
    url = f"{API_BASE}/{model}:generateContent?key={_api_key()}"
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = data["candidates"][0]["content"]["parts"]
    return " ".join(p.get("text", "") for p in parts).strip()


def ask_grounded_text(system_prompt, user_prompt, max_retries=1):
    """Grounded web-search call returning raw text. Deliberately lean (max_retries
    defaults to 1, no second sweep): the Scout makes ~10 of these per plan and a
    failure falls back to the non-grounded / YouTube path — it must never storm the
    quota or block a plan. Returns "" on total failure rather than raising, so a
    partial spine is still fine."""
    global _working_model
    models = [m for m in ("gemini-2.5-flash", "gemini-2.5-flash-lite")]
    if _working_model in models:
        models.remove(_working_model)
        models.insert(0, _working_model)
    last = None
    for model in models:
        for attempt in range(max_retries + 1):
            try:
                text = _call_grounded(model, system_prompt, user_prompt)
                _working_model = model
                return text
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="ignore")[:300]
                last = f"HTTP {e.code} from {model}: {detail}"
                if e.code in (404, 503) or (e.code == 429 and "limit: 0" in detail):
                    break                      # switch models
                if e.code in (429, 500) and attempt < max_retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            except (KeyError, IndexError, json.JSONDecodeError):
                last = f"{model} returned an unusable grounded response"
                break
    return ""   # caller degrades to the non-grounded path


def _parse_json(text):
    """Model output should be pure JSON, but strip code fences and try a light
    repair before giving up (a raised JSONDecodeError triggers a regenerate)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_repair_json(text))


def _repair_json(text):
    """Best-effort fixes for the most common model JSON slips."""
    # Remove trailing commas before } or ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    # Clip to the outermost JSON object/array (drop stray prose before/after)
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start > 0:
        text = text[start:]
    return text
