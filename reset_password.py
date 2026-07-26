"""Set a new password for one account. Run it on your laptop.

    python reset_password.py                 # lists the accounts, then asks
    python reset_password.py "faiz ahmed"    # straight to that account
    python reset_password.py --local         # the local dev accounts instead of prod

WHY THIS EXISTS
MentorOS has no email server, so it has no "forgot password" link. Without this
script, a forgotten password means hand-editing the database — which is exactly
the kind of chore that pushes people toward auth systems far riskier than a
password field. This is the whole recovery story, in one file, offline.

WHAT IT TOUCHES
One `$set` of `pw_hash` on ONE document in the `users` collection. It never
reads, writes or even opens the `state` collection, so your plan, XP, streak
and backups cannot be affected by running it — the worst case is you set a
password you then forget again.

NOTE THE ENV VAR: MONGO_URI_BACKUP, not MONGO_URI — the same rule backup.py
follows. If the local .env held MONGO_URI, then `python app.py` on this laptop
would connect to PRODUCTION and every local test would rewrite the real plan.
Only these two scripts talk to prod.

The password is read with getpass, so it is never echoed to the screen and
never lands in your shell history. Only the hash is stored, never the password
itself — the same scrypt hashing the app uses at signup.
"""

import getpass
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_LEN = 8   # matches the signup rule in app.py


def _load_env():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        sys.exit("No .env file found next to reset_password.py.")
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _local_users_path():
    return os.path.join(HERE, "mentoros_data", "_users.json")


def _connect():
    """Returns (kind, handle). kind is 'mongo' or 'local'."""
    if "--local" in sys.argv:
        path = _local_users_path()
        if not os.path.exists(path):
            sys.exit(f"No local accounts file at {path} - sign up locally first.")
        return "local", path

    _load_env()
    uri = os.environ.get("MONGO_URI_BACKUP", "").strip()
    if not uri:
        sys.exit(
            "MONGO_URI_BACKUP is not in your .env.\n"
            "Copy it from the Render dashboard: your service -> Environment -> MONGO_URI,\n"
            "then add this line to .env (note the _BACKUP suffix):\n"
            "  MONGO_URI_BACKUP=mongodb+srv://...\n"
            "Or pass --local to reset a local development account instead."
        )
    try:
        from pymongo import MongoClient
    except ImportError:
        sys.exit("pymongo isn't installed. Run:  pip install -r requirements.txt")
    # same query-string strip as storage.py — pasted Atlas URIs often carry
    # glued-together options
    client = MongoClient(uri.split("?")[0], serverSelectionTimeoutMS=20000)
    return "mongo", client["mentoros"]["users"]


def _list_accounts(kind, handle):
    if kind == "mongo":
        return [(d["_id"], d.get("name", d["_id"]), bool(d.get("pw_hash")))
                for d in handle.find({}, {"name": 1, "pw_hash": 1})]
    with open(handle, encoding="utf-8") as f:
        users = json.load(f)
    return [(uid, d.get("name", uid), bool(d.get("pw_hash"))) for uid, d in users.items()]


def _set_hash(kind, handle, uid, pw_hash):
    if kind == "mongo":
        # $set, NOT replace_one: a replace would drop every other field on the
        # user document. storage.save_notifications_for follows the same rule
        # and its comment explains why.
        res = handle.update_one({"_id": uid}, {"$set": {"pw_hash": pw_hash}})
        return res.matched_count == 1
    with open(handle, encoding="utf-8") as f:
        users = json.load(f)
    if uid not in users:
        return False
    users[uid]["pw_hash"] = pw_hash
    with open(handle, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
    return True


def main():
    try:
        from werkzeug.security import generate_password_hash
    except ImportError:
        sys.exit("werkzeug isn't installed. Run:  pip install -r requirements.txt")

    kind, handle = _connect()
    where = "PRODUCTION" if kind == "mongo" else "local development"
    accounts = _list_accounts(kind, handle)
    if not accounts:
        sys.exit(f"No accounts found in {where}.")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    uid = args[0].strip().lower() if args else ""

    if not uid:
        print(f"Accounts in {where}:")
        for a_uid, a_name, has_pw in accounts:
            print(f"   {a_uid}    (display name: {a_name}){'' if has_pw else '   [no password set]'}")
        print()
        uid = input("Which account? ").strip().lower()

    match = next((a for a in accounts if a[0] == uid), None)
    if not match:
        sys.exit(f"No account with id {uid!r}. The id is the name, lowercased.")

    print(f"\nResetting the password for {match[1]!r} in {where}.")
    print("This changes nothing else - the plan, XP, streak and backups are untouched.")
    if input("Type yes to continue: ").strip().lower() != "yes":
        sys.exit("Cancelled. Nothing was changed.")

    pw = getpass.getpass("New password (not shown): ")
    if len(pw) < MIN_LEN:
        sys.exit(f"Too short - use at least {MIN_LEN} characters, same as signup.")
    if getpass.getpass("Type it again: ") != pw:
        sys.exit("They didn't match. Nothing was changed.")

    if not _set_hash(kind, handle, uid, generate_password_hash(pw)):
        sys.exit("The account vanished between listing and writing - nothing was changed.")

    print(f"\nDone. Sign in as {match[1]!r} with the new password.")
    print("Write it down somewhere - this script is the only way back in.")


if __name__ == "__main__":
    main()
