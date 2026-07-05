"""YouTube Data API v3 — find the best video for a lesson topic, WITH its length
and chapter markers, so the mentor can tell the student exactly what to watch
today (and what to skip / continue later).

If no YOUTUBE_API_KEY is set (or the API fails), callers fall back to search
links, so this can never break a lesson.
Quota: search = 100 units, the videos lookup = ~1 unit. Two searches/lesson,
cached with the lesson.
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request

_API = "https://www.googleapis.com/youtube/v3"


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


def search_videos(query, max_results=2):
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    try:
        found = _get("search", {
            "part": "snippet", "q": query, "type": "video",
            "maxResults": max_results, "relevanceLanguage": "en", "safeSearch": "moderate",
        })
        ids = [it["id"]["videoId"] for it in found.get("items", [])
               if it.get("id", {}).get("videoId")]
        if not ids:
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
        return videos
    except Exception:
        return []  # graceful fallback — search links still work
