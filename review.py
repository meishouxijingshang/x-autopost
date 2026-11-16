"""
投稿ファイルが追加・変更されたら、確認用Issueにプレビューを投稿する
（内容が変わるたびに新しいプレビューが付き、OKはやり直しになる）
"""
from datetime import datetime
from pathlib import Path

import ghapi
from post import JST, SLOT_HOURS, parse_posts, x_weight

POSTS_DIR = Path(__file__).parent / "posts"


def render(date_str: str, posts: list[str], h: str) -> str:
    lines = [f"### {date_str} の投稿プレビュー", ""]
    for i, hour in enumerate(SLOT_HOURS):
        if i < len(posts):
            w = x_weight(posts[i])
            warn = " ⚠️ **文字数オーバー**" if w > 280 else ""
            lines += [f"**{i + 1}. {hour}時台**（全角換算 {(w + 1) // 2}/140字）{warn}",
                      "", "> " + posts[i].replace("\n", "\n> "), ""]
        else:
            lines += [f"**{i + 1}. {hour}時台**：投稿なし（スキップ）", ""]
    if len(posts) > len(SLOT_HOURS):
        lines += [f"⚠️ 投稿が{len(posts)}件あります。6件目以降は投稿されません。", ""]
    lines += ["---", "問題なければ **OK** とコメントしてください。", f"{ghapi.MARK} {h} -->"]
    return "\n".join(lines)


def main():
    today = datetime.now(JST).strftime("%Y-%m-%d")
    for path in sorted(POSTS_DIR.glob("*.txt")):
        date_str = path.stem
        if date_str < today:
            continue
        text = path.read_text(encoding="utf-8")
        h = ghapi.content_hash(text)
        issue = ghapi.find_issue(date_str) or ghapi.create_issue(date_str)
        cs = ghapi.comments(issue["number"])
        if ghapi.latest_preview_hash(cs) == h:
            print(f"{date_str}: 変更なし")
            continue
        ghapi.comment(issue["number"], render(date_str, parse_posts(text), h))
        print(f"{date_str}: プレビューを投稿しました（Issue #{issue['number']}）")


if __name__ == "__main__":
    main()
