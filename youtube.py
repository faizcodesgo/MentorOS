"""YouTube Data API v3 — find the real best videos for a lesson topic.

If no YOUTUBE_API_KEY is set (or the API fails), callers fall back to
search links, so this can never break a lesson.
Quota math: search costs 100 units of the free 10,000/day = 100 searches/day.
A lesson uses at most 2 searches, done once and cached with the lesson.
"""
import html
import json
import os
import urllib.parse
import urllib.request


def search_videos(query, max_results=2):
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "relevanceLanguage": "en",
        "safeSearch": "moderate",
        "key": key,
    })
    try:
        with urllib.request.urlopen(
            f"https://www.googleapis.com/youtube/v3/search?{params}", timeout=15
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        videos = []
        for item in data.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            snippet = item.get("snippet") or {}
            if video_id:
                videos.append({
                    "title": html.unescape(snippet.get("title", "")),
                    "channel": html.unescape(snippet.get("channelTitle", "")),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                })
        return videos
    except Exception:
        return []  # graceful fallback — search links still work
