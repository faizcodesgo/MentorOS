"""One-time empirical probe of Gemini grounding — the precondition RESOURCES-SPEC.md
slice 2 requires before any Scout code is written. Confirms, against the real key:

  1. Does `tools:[{google_search:{}}]` work on gemini-2.5-flash and return
     groundingMetadata with source URLs?
  2. Does grounding + responseMimeType:application/json really 400 (forcing the
     Scout's 2-call shape)?
  3. What do the groundingChunks URIs actually look like (redirect URLs?)?

Run:  python tools/grounding_probe.py
Spends a few grounded requests of the daily free quota. Read-only search queries.
"""
import json
import os
import urllib.request
import urllib.error

# load .env exactly like app.py
_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env):
    for line in open(_env, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

KEY = os.environ["GEMINI_API_KEY"].strip()
MODEL = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"


def call(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")[:800]


PROMPT = ("What is the single best FREE, no-login beginner resource for learning Git and "
          "GitHub, available in India? Name it and give its URL.")

print("=" * 70)
print("TEST 1 — grounding ON, no JSON mime")
code, data = call({
    "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
    "tools": [{"google_search": {}}],
    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512},
})
print("HTTP", code)
if isinstance(data, dict):
    cand = (data.get("candidates") or [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    text = " ".join(p.get("text", "") for p in parts)
    print("TEXT:", text[:300].replace("\n", " "))
    gm = cand.get("groundingMetadata", {})
    print("groundingMetadata keys:", list(gm.keys()))
    print("webSearchQueries:", gm.get("webSearchQueries"))
    chunks = gm.get("groundingChunks", [])
    print("groundingChunks count:", len(chunks))
    for c in chunks[:3]:
        w = c.get("web", {})
        print("   uri:", w.get("uri", "")[:90])
        print("   title:", w.get("title", ""))
else:
    print("BODY:", data)

print("=" * 70)
print("TEST 1b — grounding ON, room to finish (do chunks appear? URL in prose?)")
import re
code1b, data1b = call({
    "contents": [{"role": "user", "parts": [{"text": PROMPT + " State the full https URL explicitly."}]}],
    "tools": [{"google_search": {}}],
    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500},
})
print("HTTP", code1b)
if isinstance(data1b, dict):
    cand = (data1b.get("candidates") or [{}])[0]
    text = " ".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    print("FULL TEXT:", text[:600].replace("\n", " "))
    print("finishReason:", cand.get("finishReason"))
    gm = cand.get("groundingMetadata", {})
    print("gm keys:", list(gm.keys()))
    print("chunks:", len(gm.get("groundingChunks", [])))
    for c in gm.get("groundingChunks", [])[:3]:
        print("   uri:", c.get("web", {}).get("uri", "")[:90])
    urls = re.findall(r"https?://[^\s)>\]]+", text)
    print("URLs found in PROSE:", urls[:5])

print("=" * 70)
print("TEST 2 — grounding ON + responseMimeType JSON (expect 400)")
code2, data2 = call({
    "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
    "tools": [{"google_search": {}}],
    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 256,
                         "responseMimeType": "application/json"},
})
print("HTTP", code2)
print("BODY:", data2 if isinstance(data2, str) else json.dumps(data2)[:400])

print("=" * 70)
print("VERDICT")
print("  grounding works:", code == 200)
print("  json-incompatible (needs 2-call shape):", code2 == 400)
