"""Dump the live production database to a file on the Desktop.

    python backup.py

Read-only: it never writes to Mongo. Run it before anything that touches
storage.py, and any time you want a copy you can hold onto.

Why this exists: Atlas M0 (the free tier) has NO automated backups, and every
save is a whole-document replace. Without this, the only copy of a 50-day plan
lives in one document in one cluster, and a bad write is permanent.

Restore is deliberately NOT automated. If you ever need it, open the JSON, find
the "state" object, and hand it back — a one-command restore is exactly the kind
of thing that gets run by accident.

NOTE the env var: MONGO_URI_BACKUP, not MONGO_URI. If the local .env held
MONGO_URI, then `python app.py` on this laptop would connect to PRODUCTION and
every local test would rewrite the real plan. Local dev uses mentoros_data.json;
only this script talks to prod.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_env():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        sys.exit("No .env file found next to backup.py.")
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def main():
    _load_env()
    uri = os.environ.get("MONGO_URI_BACKUP", "").strip()
    if not uri:
        sys.exit(
            "MONGO_URI_BACKUP is not in your .env.\n"
            "Copy it from the Render dashboard: your service -> Environment -> MONGO_URI,\n"
            "then add this line to .env (note the _BACKUP suffix):\n"
            "  MONGO_URI_BACKUP=mongodb+srv://..."
        )
    try:
        from pymongo import MongoClient
    except ImportError:
        sys.exit("pymongo isn't installed. Run:  pip install -r requirements.txt")

    # same query-string strip as storage.py — pasted Atlas URIs often carry
    # glued-together options
    client = MongoClient(uri.split("?")[0], serverSelectionTimeoutMS=20000)
    docs = list(client["mentoros"]["state"].find({}))
    if not docs:
        sys.exit("Connected, but the collection is empty. Nothing backed up — check the URI.")

    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    out = os.path.join(os.path.expanduser("~"), "Desktop", f"mentoros-backup-{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2, default=str, ensure_ascii=False)

    print(f"Backed up {len(docs)} document(s) -> {out}")
    for d in docs:
        st = d.get("state", {})
        plan = st.get("plan") or {}
        done = sum(1 for p in (st.get("progress") or {}).values() if p.get("completed"))
        print(f"  {d['_id']}: {plan.get('days', '?')} days, {done} done, "
              f"{st.get('xp', 0)} XP, {len(st.get('lessons') or {})} lessons cached")
    print(f"\n{os.path.getsize(out):,} bytes. Keep it somewhere that isn't this laptop.")


if __name__ == "__main__":
    main()
