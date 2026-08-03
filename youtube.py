"""YouTube Data API v3 — find the best video for a lesson topic, WITH its length
and chapter markers, so the mentor can tell the student exactly what to watch
today (and what to skip / continue later).

If no YOUTUBE_API_KEY is set (or the API fails), callers fall back to search
links, so this can never break a lesson.
Quota: search = 100 units, the videos lookup = ~1 unit. Two searches/lesson,
cached with the lesson.
"""
import datetime
import html
import json
import os
import re
import threading
import urllib.parse
import urllib.request

_API = "https://www.googleapis.com/youtube/v3"

_CACHE_TTL_DAYS = 30      # a good explainer rarely dies within a month
_CACHE_MAX = 200          # keep the per-user cache from bloating the 16MB state doc
# section-video fetches fan out across up to 6 threads sharing one cache dict; the
# lock serialises the insert+trim so `sorted(cache.items())` can't race another
# thread's insert ("dict changed size during iteration"), which would silently drop
# an already-fetched (already-quota-paid) video.
_CACHE_LOCK = threading.Lock()


def _norm(query):
    """The query, normalized to the unit that actually costs quota."""
    return " ".join((query or "").lower().split())


def _cache_get(cache, key):
    if not isinstance(cache, dict):
        return None
    entry = cache.get(key)
    if not entry:
        return None
    try:
        ts = datetime.datetime.fromisoformat(entry.get("ts"))
        if (datetime.datetime.now(datetime.timezone.utc) - ts).days > _CACHE_TTL_DAYS:
            return None
    except Exception:
        return None
    return entry.get("videos")


def _cache_put(cache, key, videos):
    if not isinstance(cache, dict):
        return
    with _CACHE_LOCK:
        cache[key] = {"videos": videos,
                      "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        # trim oldest by timestamp so the cache can't grow without bound
        if len(cache) > _CACHE_MAX:
            for k, _ in sorted(cache.items(), key=lambda kv: kv[1].get("ts", ""))[:len(cache) - _CACHE_MAX]:
                cache.pop(k, None)


def _get(path, params):
    params["key"] = os.environ.get("YOUTUBE_API_KEY", "").strip()
    url = f"{_API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _duration(iso):
    """ISO-8601 'PT1H23M45S' -> ('1h 23m', 5025)."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return "", 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    secs = h * 3600 + mi * 60 + s
    if h and mi:
        label = f"{h}h {mi}m"
    elif h:
        label = f"{h}h"
    elif mi:
        label = f"{mi}m"
    else:
        label = f"{s}s"
    return label, secs


def _chapters(description):
    """Pull chapter markers from a video description (lines like '12:34 Title').
    YouTube only treats them as real chapters when the first is at 0:00 and there
    are >=3, so we honor that before trusting them."""
    found = []
    for line in (description or "").splitlines():
        m = re.match(r"\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\s*[-–—)\].]*\s*(.+)", line)
        if m:
            label = m.group(2).strip()
            if label:
                found.append({"t": m.group(1), "label": label[:60]})
    if len(found) >= 3 and found[0]["t"].lstrip("0:") in ("", "0"):
        return found[:20]
    return []


def video_id_from_url(url):
    """The 11-char YouTube id from a watch / youtu.be / embed URL, or None."""
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None


def video_details(video_id, cache=None, guard=None):
    """Real title/channel/duration/chapters for a KNOWN video id — one videos.list
    call (~1 unit, vs search's 100). Used to enrich a URL the Scout already found,
    so a resource card shows 'freeCodeCamp: Git Crash Course · 1h 09m' instead of
    a bare domain. Cached like search_videos; graceful None on any failure."""
    apikey = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not apikey or not video_id:
        return None
    key = "vid:" + video_id
    cached = _cache_get(cache, key)
    if cached is not None:
        return cached[0] if cached else None
    if guard is not None and not guard():
        return None
    try:
        det = _get("videos", {"part": "snippet,contentDetails", "id": video_id})
        items = det.get("items", [])
        if not items:
            _cache_put(cache, key, [])            # stable miss — cache it
            return None
        it = items[0]
        sn = it.get("snippet") or {}
        label, secs = _duration((it.get("contentDetails") or {}).get("duration"))
        v = {"title": html.unescape(sn.get("title", "")),
             "channel": html.unescape(sn.get("channelTitle", "")),
             "url": f"https://www.youtube.com/watch?v={video_id}",
             "duration": label, "duration_seconds": secs,
             "chapters": _chapters(sn.get("description", ""))}
        _cache_put(cache, key, [v])
        return v
    except Exception:
        return None


def search_videos(query, max_results=2, cache=None, guard=None):
    """Find the best video(s) for a query, WITH length + chapters.

    cache: an optional dict (the user's state["yt_cache"]) — a hit costs ZERO
      YouTube quota, which is what makes lesson REGENERATION free. Mutated in place.
    guard: an optional zero-arg callable returning True if a fresh search is within
      the daily quota budget. Returns [] (→ caller falls back to a search LINK) when
      it says no, so a bug can never blow the shared 10,000-units/day quota.
    """
    apikey = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not apikey:
        return []
    key = _norm(query)
    cached = _cache_get(cache, key)
    if cached is not None:
        return cached
    if guard is not None and not guard():
        return []      # over the daily budget → let the caller show a search link
    try:
        found = _get("search", {
            "part": "snippet", "q": query, "type": "video",
            "maxResults": max_results, "relevanceLanguage": "en", "safeSearch": "moderate",
        })
        ids = [it["id"]["videoId"] for it in found.get("items", [])
               if it.get("id", {}).get("videoId")]
        if not ids:
            _cache_put(cache, key, [])   # a query that finds nothing is stable — cache it
            return []
        # one cheap follow-up gets length + chapters for exactly these videos
        det = _get("videos", {"part": "snippet,contentDetails", "id": ",".join(ids)})
        videos = []
        for it in det.get("items", []):
            sn = it.get("snippet") or {}
            label, secs = _duration((it.get("contentDetails") or {}).get("duration"))
            videos.append({
                "title": html.unescape(sn.get("title", "")),
                "channel": html.unescape(sn.get("channelTitle", "")),
                "url": f"https://www.youtube.com/watch?v={it['id']}",
                "duration": label,
                "duration_seconds": secs,
                "chapters": _chapters(sn.get("description", "")),
            })
        _cache_put(cache, key, videos)   # success → never re-spend quota on this query
        return videos
    except Exception:
        return []  # graceful fallback (do NOT cache — a transient error should retry)
