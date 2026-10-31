"""Official X API v2 follow manager. Opt-in and dry-run by default.

Required GitHub Actions secrets:
X_USER_ACCESS_TOKEN: OAuth 2.0 user access token with users.read, follows.read,
follows.write scopes (and offline.access if refresh is managed externally).
X_USER_ID: authenticated account's numeric user ID.

Optional variables:
X_TARGET_USER_IDS: comma-separated numeric IDs to follow (explicit allow-list).
X_FOLLOW_MIN_FOLLOWERS: minimum public follower count for follow candidates (default 1000).
X_CLEANUP_NONFOLLOWERS: true to remove only non-reciprocal follows under 1000 followers.
X_DAILY_ACTION_CAP: requested cap, clamped to 50 combined actions/day.
X_FOLLOW_DRY_RUN: true by default.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

API = "https://api.x.com/2"
ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "x_follow_state.json"
HARD_DAILY_CAP = 50
TIMEOUT = 30


def env(name, default=""):
    return os.getenv(name, default).strip()


def _headers():
    token = env("X_USER_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("X_USER_ACCESS_TOKEN eksik. X_AUTH_TOKEN/X_CT0 çerezleri artık kullanılmıyor.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request(method, path, *, params=None, body=None):
    response = requests.request(
        method, f"{API}{path}", headers=_headers(), params=params, json=body, timeout=TIMEOUT
    )
    if response.status_code == 429:
        raise RuntimeError("X API 429 rate limit: işlem güvenlik için durduruldu; daha sonra tekrar dene.")
    if response.status_code in (401, 403):
        raise RuntimeError(f"X API yetki hatası {response.status_code}: OAuth kullanıcı token'ı ve follows.read/write izinlerini kontrol et.")
    response.raise_for_status()
    return response.json() if response.content else {}


def _paginate(path, params):
    values, token = [], None
    while True:
        query = dict(params)
        query["max_results"] = 1000
        if token:
            query["pagination_token"] = token
        result = _request("GET", path, params=query)
        values.extend(result.get("data", []))
        token = (result.get("meta") or {}).get("next_token")
        if not token:
            return values


def _load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"date": "", "actions": 0, "history": []}


def _save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _users_by_id(ids):
    found = {}
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        if not batch:
            continue
        result = _request(
            "GET", "/users", params={"ids": ",".join(batch), "user.fields": "public_metrics"}
        )
        for user in result.get("data", []):
            found[user["id"]] = user
    return found


def run():
    if env("ENABLE_X_AUTO_FOLLOW").lower() != "true":
        print("🛡️ X follow manager kapalı. ENABLE_X_AUTO_FOLLOW=true olmadan işlem yapılmaz.")
        return

    user_id = env("X_USER_ID")
    if not user_id.isdigit():
        raise RuntimeError("X_USER_ID sayısal kullanıcı ID'si olarak tanımlanmalı.")

    dry_run = env("X_FOLLOW_DRY_RUN", "true").lower() != "false"
    requested_cap = int(env("X_DAILY_ACTION_CAP", "10"))
    cap = min(HARD_DAILY_CAP, max(1, requested_cap))
    today = datetime.now(timezone.utc).date().isoformat()
    state = _load_state()
    if state.get("date") != today:
        state = {"date": today, "actions": 0, "history": state.get("history", [])}
    remaining = max(0, cap - int(state.get("actions", 0)))

    following = _paginate(f"/users/{user_id}/following", {"user.fields": "public_metrics"})
    following_ids = {u["id"] for u in following}
    followers = _paginate(f"/users/{user_id}/followers", {"user.fields": "public_metrics"})
    follower_ids = {u["id"] for u in followers}

    target_ids = list(dict.fromkeys(x for x in env("X_TARGET_USER_IDS").split(",") if x.strip().isdigit()))
    min_followers = max(0, int(env("X_FOLLOW_MIN_FOLLOWERS", "1000")))
    cleanup = env("X_CLEANUP_NONFOLLOWERS", "false").lower() == "true"

    follow_candidates = [x for x in target_ids if x not in following_ids]
    metrics = _users_by_id(list(dict.fromkeys(follow_candidates + list(following_ids)))) if (follow_candidates or cleanup) else {}

    plan = []
    for target_id in follow_candidates:
        user = metrics.get(target_id, {})
        count = (user.get("public_metrics") or {}).get("followers_count", 0)
        if count >= min_followers:
            plan.append(("follow", target_id, user.get("username", "?"), count))

    if cleanup:
        for target_id in following_ids - follower_ids:
            user = metrics.get(target_id, {})
            count = (user.get("public_metrics") or {}).get("followers_count", 0)
            if count < 1000:
                plan.append(("unfollow", target_id, user.get("username", "?"), count))

    print(f"X hesabı: {user_id} | takip edilen: {len(following_ids)} | seni takip eden: {len(follower_ids)}")
    print(f"Plan: {len(plan)} işlem | günlük kalan: {remaining} | limit: {cap} | dry_run={dry_run}")
    for action, target_id, username, count in plan[:remaining]:
        print(f"{'[DRY-RUN] ' if dry_run else ''}{action} @{username} (followers={count}, id={target_id})")
        if dry_run:
            continue
        if action == "follow":
            _request("POST", f"/users/{user_id}/following", body={"target_user_id": target_id})
        else:
            _request("DELETE", f"/users/{user_id}/following/{target_id}")
        state["actions"] = int(state.get("actions", 0)) + 1
        state.setdefault("history", []).append({
            "date": today, "action": action, "target_user_id": target_id,
            "username": username, "followers_count": count
        })
        state["history"] = state["history"][-1000:]
        _save_state(state)

    print("Bitti. API izinleri/erişimi uygun değilse işlem yapılmaz; 429 durumunda tüm tur durdurulur.")


if __name__ == "__main__":
    run()
