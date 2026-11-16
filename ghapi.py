"""GitHub API の小さなヘルパー（確認用Issueの作成・承認チェック）"""
import base64
import hashlib
import json
import os
import urllib.parse
import urllib.request

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
BOT = "github-actions[bot]"
APPROVE_WORDS = {"ok", "ｏｋ", "承認", "おけ"}
APPROVER_ROLES = {"OWNER", "MEMBER", "COLLABORATOR"}
MARK = "<!-- preview:"


def _req(method, path, data=None):
    url = path if path.startswith("http") else f"{API}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or "null")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:12]


def issue_title(date_str: str) -> str:
    return f"投稿確認 {date_str}"


def get_file(path: str) -> str | None:
    """リポジトリ上の最新のファイル内容を取得（待機中に編集された場合にも対応）"""
    try:
        d = _req("GET", f"/repos/{REPO}/contents/{urllib.parse.quote(path)}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return base64.b64decode(d["content"]).decode("utf-8")


def find_issue(date_str: str):
    title = issue_title(date_str)
    for page in range(1, 4):
        items = _req("GET", f"/repos/{REPO}/issues?state=all&per_page=100&page={page}")
        for it in items:
            if it["title"] == title and "pull_request" not in it:
                return it
        if len(items) < 100:
            break
    return None


def create_issue(date_str: str):
    return _req("POST", f"/repos/{REPO}/issues", {
        "title": issue_title(date_str),
        "body": (f"posts/{date_str}.txt の投稿内容の確認用です。\n\n"
                 "下のコメントの内容で問題なければ **OK** とコメントしてください。\n"
                 "OKがない投稿は投稿されません。ファイルを直すと再確認になります。"),
    })


def comments(issue_number: int):
    return _req("GET", f"/repos/{REPO}/issues/{issue_number}/comments?per_page=100")


def comment(issue_number: int, body: str):
    _req("POST", f"/repos/{REPO}/issues/{issue_number}/comments", {"body": body})


def close_issue(issue_number: int):
    _req("PATCH", f"/repos/{REPO}/issues/{issue_number}", {"state": "closed"})


def latest_preview_hash(cs) -> str | None:
    for c in reversed(cs):
        if c["user"]["login"] == BOT and MARK in c["body"]:
            return c["body"].split(MARK, 1)[1].split("-->", 1)[0].strip()
    return None


def is_approved(cs, h: str) -> bool:
    """現在の内容(h)のプレビューより後に、オーナーの「OK」コメントがあるか"""
    idx = None
    for i, c in enumerate(cs):
        if c["user"]["login"] == BOT and f"{MARK} {h} -->" in c["body"]:
            idx = i
    if idx is None:
        return False
    for c in cs[idx + 1:]:
        word = c["body"].strip().strip("。！!").lower()
        if word in APPROVE_WORDS and c.get("author_association") in APPROVER_ROLES:
            return True
    return False
