"""Resource Mentor — discovery + verification helpers (RESOURCES-SPEC.md).

This module holds the *pure* pieces: normalize a topic, pull URLs out of grounded
prose, and verify a URL is really reachable. The Scout endpoint and the Monitor
live in app.py (they need request state); they call into here.

No model-authored URL ever reaches the UI unverified — verify_url is the gate.
"""
import concurrent.futures
import re
import urllib.request
import urllib.error

# strip these from a topic tag so "For Loops", "basic loops", "loops concept" all
# collapse to one cache key. Mirrors dna.norm_topic's spirit (kept separate so the
# two can diverge — DNA keys quiz topics, this keys discovery queries).
_QUALIFIERS = {"the", "a", "an", "basic", "basics", "intro", "introduction", "to",
               "using", "concept", "concepts", "advanced", "simple", "fundamentals",
               "of", "and", "in", "with", "for", "your", "learn", "learning"}


def normalize_topic(topic):
    """A stable, comparable cache key for a topic — lowercase, de-punctuated,
    qualifier-stripped. Two users learning the same thing must hit the same key."""
    t = (topic or "general").lower().strip()
    t = re.sub(r"[^a-z0-9+#\- ]", " ", t)      # keep +/# (c++, c#) — real topic names
    t = re.sub(r"\s+", " ", t).strip()
    words = [w for w in t.split(" ") if w and w not in _QUALIFIERS]
    return " ".join(words) or "general"


def extract_urls(text):
    """Pull https URLs out of grounded prose (where the real, non-redirect links
    live — see the probe). Strips trailing markdown/punctuation the model leaves
    on a URL (…evk** or …evk). and de-dupes, order-preserving."""
    raw = re.findall(r"https?://[^\s<>\])]+", text or "")
    seen, out = set(), []
    for u in raw:
        u = u.rstrip(".,);*_")            # trailing markdown/sentence punctuation
        u = u.rstrip("*")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


_UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/120.0 Mobile Safari/537.36")
# a redirect landing on one of these is a login/paywall wall -> not a usable resource
_WALL = ("/login", "/signin", "/sign-in", "/account", "/subscribe", "/checkout",
         "/pricing", "accounts.google", "/auth")


def verify_url(url, timeout=5):
    """Three-way verdict (RESOURCES-SPEC.md §3):
      "live"       — 2xx/3xx, reachable, not walled          -> use it
      "unverified" — 401/403/405/429/challenge               -> keep but mark (a 403
                     is evidence the site is alive enough to DEFEND itself; a real
                     good resource behind Cloudflare must not be dropped as dead)
      "dead"       — DNS fail, refused, 404/410, login-wall  -> drop
    A ranged GET (not HEAD — CDNs mishandle HEAD) with a browser UA; ~1KB."""
    try:
        req = urllib.request.Request(url, method="GET", headers={
            "User-Agent": _UA, "Range": "bytes=0-1023", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.geturl() or url                 # after redirects
            if any(w in final.lower() for w in _WALL):
                return "dead"                            # redirected into a wall
            return "live"                                # 2xx/3xx
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 405, 429):
            return "unverified"                          # alive enough to refuse a bot
        if e.code in (404, 410):
            return "dead"
        return "unverified"                              # 5xx/other — don't assert dead
    except Exception:
        return "dead"                                    # DNS fail, refused, timeout


def verify_urls(urls, timeout=5, max_workers=10):
    """Verify many URLs concurrently inside one request (a ThreadPoolExecutor does
    NOT consume gunicorn request slots — same pattern as the parallel lesson gen).
    Returns {url: verdict}. Wave bounded by the per-URL timeout."""
    urls = list(dict.fromkeys(urls))                     # de-dupe, keep order
    if not urls:
        return {}
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(urls))) as ex:
        futs = {ex.submit(verify_url, u, timeout): u for u in urls}
        for fut in concurrent.futures.as_completed(futs):
            out[futs[fut]] = fut.result()
    return out


def _platform(url):
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u: return "youtube"
    if "github.com" in u: return "github"
    if "freecodecamp" in u: return "freecodecamp"
    if "khanacademy" in u: return "khan"
    if "nptel" in u: return "nptel"
    if any(d in u for d in ("docs.", "/docs", "developer.", ".dev/")): return "docs"
    return "web"


def _domain(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return (m.group(1) if m else url).replace("www.", "")


def _why(prose):
    """The first sentence of the grounded prose — the mentor's one-line reason."""
    s = re.split(r"(?<=[.!?])\s", (prose or "").strip())
    return (s[0][:200] if s and s[0] else "").strip()


def _discover_chapter(phase, level_notes, hours_per_day, days, ask_fn, verify_fn,
                      cache_get, cache_put, cache_lock, enrich_fn=None):
    """Find ONE verified resource for a chapter, or []. Grounded call + verify,
    with a topic-keyed cache. Runs in a worker thread, so all I/O is local to it."""
    import prompts
    name = (phase.get("name") or "").strip() or "this chapter"
    key = normalize_topic(name + " " + (phase.get("focus") or ""))
    if cache_get:
        hit = cache_get(key)
        if hit is not None:
            return hit
    prose = ask_fn(prompts.SCOUT_SYSTEM,
                   prompts.scout_prompt(name, phase.get("focus", ""),
                                        level_notes, hours_per_day, days))
    urls = extract_urls(prose)
    verdicts = verify_fn(urls) if urls else {}
    top = next((u for u in urls if verdicts.get(u) in ("live", "unverified")), None)
    resolved = []
    if top:
        entry = {"url": top, "title": _domain(top), "platform": _platform(top),
                 "kind": "video" if _platform(top) == "youtube" else "link",
                 "why": _why(prose), "status": verdicts.get(top, "unverified")}
        # enrich a YouTube pick with its REAL title + duration (+ chapters), so the
        # card reads "freeCodeCamp: Git Crash Course · 1h 09m" not "youtube.com"
        if enrich_fn and entry["platform"] == "youtube":
            meta = enrich_fn(top)
            if meta and meta.get("title"):
                entry["title"] = meta["title"]
                entry["channel"] = meta.get("channel", "")
                entry["duration"] = meta.get("duration", "")
                entry["duration_seconds"] = meta.get("duration_seconds", 0)
                entry["has_chapters"] = bool(meta.get("chapters"))
        resolved = [entry]
        if cache_put:
            with cache_lock:                       # local-file cache isn't thread-safe
                cache_put(key, resolved)
    return resolved


def build_spine(phases, level_notes, hours_per_day, days,
                ask_fn=None, verify_fn=None, cache_get=None, cache_put=None,
                budget=None, max_workers=4, enrich_fn=None):
    """Build (resource_spine, resource_slots) for a plan — one verified pick per
    chapter, chapters discovered IN PARALLEL (cap 4, like generate_all) so an
    8-chapter plan resolves in ~2 waves instead of 8 sequential grounded calls.
    Every dependency is injectable so tests run with ZERO quota. `budget` seconds
    time-boxes the whole wave; chapters not done in time stay text-led (the feature
    is additive — a thin spine just means those days behave like today). A chapter
    that yields no verifiable URL is skipped."""
    import threading
    import gemini
    ask_fn = ask_fn or gemini.ask_grounded_text
    verify_fn = verify_fn or verify_urls
    lock = threading.Lock()

    # chapter day-ranges up front, so the (parallel) resolution order can't affect
    # slot assignment — spine/slots are assembled in chapter order afterwards
    ranges, start = [], 1
    for phase in phases:
        pdays = int(phase.get("days") or 1)
        ranges.append((start, start + pdays - 1))
        start += pdays

    results = {}
    # NOT a `with` block: its __exit__ waits for every thread, which would defeat
    # the budget if a grounded call hangs near its 120s socket timeout. We collect
    # whatever finished within `budget`, then shut down WITHOUT waiting — any
    # still-running thread just finishes into the cache, harmlessly.
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    futs = {ex.submit(_discover_chapter, ph, level_notes, hours_per_day, days,
                      ask_fn, verify_fn, cache_get, cache_put, lock, enrich_fn): i
            for i, ph in enumerate(phases)}
    try:
        for fut in concurrent.futures.as_completed(futs, timeout=budget):
            try:
                results[futs[fut]] = fut.result()
            except Exception:
                results[futs[fut]] = []          # one chapter's failure is not the plan's
    except concurrent.futures.TimeoutError:
        pass                                     # budget spent — take what finished
    ex.shutdown(wait=False, cancel_futures=True)

    spine, slots = [], {}
    for pidx, phase in enumerate(phases):
        resolved = results.get(pidx) or []
        if not resolved:
            continue
        sid = f"r{pidx}"
        spine.append({"id": sid, "chapter": pidx, **resolved[0]})
        s, e = ranges[pidx]
        slot_day = next((d for d in range(s, e + 1) if d > 1), None)   # never day 1
        if slot_day is not None:
            slots[str(slot_day)] = {"spine": sid, "segment": 0, "modality": "resource"}
    return spine, slots
