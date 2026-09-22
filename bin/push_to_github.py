#!/usr/bin/env python3
"""Push working-copy changes to wes-chen/long-play via the GitHub Contents API.

Usage: python3 bin/push_to_github.py "commit message"

Pushes all tracked modifications, new files, and deletions. Private listening
data can never be committed: denylisted paths are skipped with a loud warning.

After a clean push, the local clone is reset to origin/main so the next
`git pull --ff-only` in cron bodies fast-forwards cleanly.
"""
import base64
import fnmatch
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response  # noqa: E402

HOST = "api.github.com"
REPO = "wes-chen/long-play"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Never commit these, even if they appear in the working copy.
DENYLIST = [
    "samples.jsonl", "watchlist.json", "rollups/*",
    "*.log", ".env", "*secret*", "*token*", "*credential*", "*private*",
]


def api(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"https://{HOST}{path}", data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "muse-agent")
    if body:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, "custom.github", allowed_hosts=[HOST])
    try:
        with urllib.request.urlopen(req) as r:
            return {"ok": True, "data": read_json_response(r)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "code": e.code, "data": e.read().decode()[:300]}


def denied(path):
    return any(fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(os.path.basename(path), pat)
               for pat in DENYLIST)


def changed_files():
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                         capture_output=True, text=True)
    files = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        status, path = line[:2], line[3:].strip().strip('"')
        # handle renames: "R  old -> new"
        if "->" in path:
            path = path.split("->")[-1].strip().strip('"')
        files.append((status.strip(), path))
    return files


def push_file(path, message):
    full = os.path.join(ROOT, path)
    cur = api("GET", f"/repos/{REPO}/contents/{path}?ref=main")
    with open(full, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    payload = {"message": message, "content": content}
    if cur["ok"]:
        payload["sha"] = cur["data"]["sha"]
    r = api("PUT", f"/repos/{REPO}/contents/{path}", payload)
    return r


def delete_file(path, message):
    cur = api("GET", f"/repos/{REPO}/contents/{path}?ref=main")
    if not cur["ok"]:
        return {"ok": True, "data": {"commit": {"sha": "already-gone"}}}
    r = api("DELETE", f"/repos/{REPO}/contents/{path}",
            {"message": message, "sha": cur["data"]["sha"]})
    return r


def expand(path):
    """Expand a status path into pushable files (handles untracked dirs)."""
    full = os.path.join(ROOT, path)
    if os.path.isdir(full):
        out = []
        for dirpath, _, names in os.walk(full):
            for n in names:
                # skip nothing here; denylist is checked per-file by caller
                out.append(os.path.relpath(os.path.join(dirpath, n), ROOT))
        return sorted(out)
    return [path]


def main():
    if len(sys.argv) < 2:
        print('usage: python3 bin/push_to_github.py "commit message"')
        return 2
    message = sys.argv[1]
    files = changed_files()
    if not files:
        print("nothing to push")
        return 0

    pushed, skipped = [], []
    for status, path in files:
        for fpath in expand(path):
            if denied(fpath):
                skipped.append(fpath)
                print(f"DENYLISTED, skipping: {fpath}")
                continue
            if status == "D":
                r = delete_file(fpath, message)
                action = "deleted"
            else:
                if not os.path.isfile(os.path.join(ROOT, fpath)):
                    print(f"not a file, skipping: {fpath}")
                    continue
                r = push_file(fpath, message)
                action = "updated" if status == "M" else "created"
            if r["ok"]:
                sha = r["data"]["commit"]["sha"][:7]
                pushed.append(fpath)
                print(f"{fpath}: {action} -> {sha}")
            else:
                print(f"FAILED {fpath}: {r.get('code')} {r.get('data')}")
                return 1

    if skipped:
        print(f"warning: {len(skipped)} denylisted path(s) not pushed: {skipped}")

    # keep the clone in sync so cron `git pull --ff-only` keeps working
    still_dirty = []
    for _status, _path in changed_files():
        for _f in expand(_path):
            if _f not in skipped and _f not in pushed:
                still_dirty.append(_f)
    if not still_dirty:
        subprocess.run(["git", "fetch", "-q", "origin"], cwd=ROOT)
        subprocess.run(["git", "reset", "-q", "--hard", "origin/main"], cwd=ROOT)
        print("local clone synced to origin/main")
    else:
        print("working tree not clean (denylisted leftovers); clone left as-is")
    print(f"done: {len(pushed)} file(s) pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
