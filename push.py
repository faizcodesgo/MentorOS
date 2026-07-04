"""Web Push — send one gentle daily digest. No AI. Android-first (iOS push is
too fragile to promise). Triggered by the external cron pinger, not a worker.
"""
import datetime
import json
import os


def _vapid():
    return (os.environ.get("VAPID_PRIVATE_KEY", ""),
            os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:admin@mentoros.app"))


def send_to(subscription, title, body):
    """Send one push; returns False if the subscription is dead (410/404)."""
    from pywebpush import webpush, WebPushException
    priv, email = _vapid()
    if not priv:
        return True  # not configured — no-op, don't drop subs
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=priv,
            vapid_claims={"sub": email},
        )
        return True
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return code not in (404, 410)   # dead subscription → caller removes it
    except Exception:
        return True


def _in_quiet_hours(now, quiet):
    start, end = quiet.get("start", "22:00"), quiet.get("end", "08:00")
    t = now.strftime("%H:%M")
    if start <= end:
        return start <= t < end
    return t >= start or t < end        # window wraps midnight


def build_digest(state):
    """Decide today's ONE notification (or None). Combines the daily nudge with
    any due spaced-review recalls into a single message."""
    import reviews as review_engine

    plan = state.get("plan")
    if not plan or not plan.get("curriculum"):
        return None

    # due recalls today (same logic the warm-up uses)
    today_order = 0
    ordered = sorted(plan["curriculum"], key=lambda d: d.get("order", d["day"]))
    for d in ordered:
        if not state["progress"].get(str(d["day"]), {}).get("completed"):
            today_order = d.get("order", d["day"])   # keep x.5 revision orders intact
            break
    due = review_engine.due_items(state, today_order, limit=3) if today_order else []

    name = (state.get("profile") or {}).get("name", "")
    who = f" {name}" if name else ""
    if due:
        n = len(due)
        return ("MentorOS", f"{n} concept{'s' if n > 1 else ''} ready to recall{who} — "
                            f"a few minutes locks them in.")
    # otherwise a gentle daily nudge toward the next day's lesson
    nxt = next((d for d in ordered if not state["progress"].get(str(d["day"]), {}).get("completed")), None)
    if nxt:
        title = nxt.get("title") or "today's lesson"
        return ("MentorOS", f"Your study window is open{who} — up next: {title}.")
    return None


def run_cron(state, now=None):
    """Called by the cron endpoint. Sends at most one digest/day, respecting
    quiet hours and the user's daily time. Returns a short status dict."""
    now = now or datetime.datetime.now()
    notif = state.get("notifications") or {}
    if not notif.get("enabled") or not notif.get("subscriptions"):
        return {"sent": 0, "reason": "disabled or no subscription"}
    if _in_quiet_hours(now, notif.get("quiet_hours", {})):
        return {"sent": 0, "reason": "quiet hours"}
    if now.strftime("%H:%M") < notif.get("daily_time", "19:00"):
        return {"sent": 0, "reason": "before daily time"}

    today = now.date().isoformat()
    if notif.get("last_notified", {}).get("digest") == today:
        return {"sent": 0, "reason": "already sent today"}

    digest = build_digest(state)
    if not digest:
        return {"sent": 0, "reason": "nothing to say"}

    title, body = digest
    alive = []
    sent = 0
    for sub in notif["subscriptions"]:
        if send_to(sub, title, body):
            alive.append(sub)
            sent += 1
    notif["subscriptions"] = alive
    notif.setdefault("last_notified", {})["digest"] = today
    return {"sent": sent, "body": body}
