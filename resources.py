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
