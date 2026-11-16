"""
X 自動投稿スクリプト
- posts/YYYY-MM-DD.txt から、その日の投稿を読み込む（"---" の行で区切る）
- 投稿枠: 8時, 10時, 12時, 18時, 21時（日本時間）
- 各枠の中で「分」をランダムに決めて、その時刻まで待ってから投稿する
- 確認用Issueで「OK」とコメントされた内容だけを投稿する
"""
import os
import random
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SLOT_HOURS = [8, 10, 12, 18, 21]  # 1番目〜5番目の投稿に対応
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def x_weight(text: str) -> int:
    """Xの文字数カウント（日本語などの全角は2、半角は1）の概算"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F", "A") else 1 for c in text)


def parse_posts(raw: str) -> list[str]:
    raw = raw.replace("\r\n", "\n")
    posts = [p.strip() for p in raw.split("\n---\n")]
    return [p for p in posts if p]


def main() -> int:
    import ghapi

    # GitHubの起動は遅れることがあるので、+20分して「どの枠か」を判定
    now = datetime.now(JST)
    probe = now + timedelta(minutes=20)
    if probe.hour not in SLOT_HOURS:
        print(f"投稿枠の時間ではありません（現在 {now:%H:%M} JST）")
        return 0
    slot = SLOT_HOURS.index(probe.hour)
    date_str = probe.strftime("%Y-%m-%d")

    # 分・秒をランダムに決めて待つ
    target = probe.replace(minute=random.randint(0, 59),
                           second=random.randint(0, 59), microsecond=0)
    print(f"{date_str} 枠{slot + 1}（{probe.hour}時台）→ {target:%H:%M:%S} に投稿予定")
    wait = (target - datetime.now(JST)).total_seconds()
    if wait > 0 and not DRY_RUN:
        time.sleep(wait)

    # 待機中の編集・承認も反映するため、投稿直前に最新の内容と承認を確認
    raw = ghapi.get_file(f"posts/{date_str}.txt")
    if raw is None:
        print(f"posts/{date_str}.txt がありません")
        return 0
    posts = parse_posts(raw)
    if slot >= len(posts):
        print(f"{slot + 1} 番目の投稿がないためスキップします")
        return 0
    text = posts[slot]

    issue = ghapi.find_issue(date_str)
    h = ghapi.content_hash(raw)
    if not issue or not ghapi.is_approved(ghapi.comments(issue["number"]), h):
        print("未承認のためスキップします")
        if issue and not DRY_RUN:
            ghapi.comment(issue["number"],
                          f"⏭️ {probe.hour}時台の投稿は、OKがなかったためスキップしました。")
        return 0

    if x_weight(text) > 280:
        print(f"文字数オーバーです（全角約140字まで）:\n{text}")
        return 1

    if DRY_RUN:
        print(f"[テストモード] 承認済み。投稿予定の文:\n{text}")
        return 0

    import tweepy
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    res = client.create_tweet(text=text)
    url = f"https://x.com/i/web/status/{res.data['id']}"
    print(f"投稿しました: {url}")
    ghapi.comment(issue["number"], f"✅ {probe.hour}時台に投稿しました: {url}")
    if slot == min(len(posts), len(SLOT_HOURS)) - 1:
        ghapi.close_issue(issue["number"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
