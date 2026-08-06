import feedparser
import json
import os
import pathlib
import urllib.parse

import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_DIR = pathlib.Path(__file__).parent
KEYWORDS_FILE = BASE_DIR / "keywords.txt"
SEEN_FILE = BASE_DIR / "seen_links.json"


def load_keywords():
    return [
        line.strip()
        for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def send_telegram(text):
    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": False},
        timeout=10,
    )
    resp.raise_for_status()


def check_keyword(keyword, seen):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    new_count = 0
    for entry in feed.entries[:10]:
        if entry.link in seen:
            continue
        send_telegram(f"[{keyword}] {entry.title}\n{entry.link}")
        seen.add(entry.link)
        new_count += 1
    return new_count


def main():
    keywords = load_keywords()
    seen = load_seen()
    total_new = 0
    for kw in keywords:
        total_new += check_keyword(kw, seen)
    save_seen(seen)
    print(f"checked {len(keywords)} keywords, sent {total_new} new articles")


if __name__ == "__main__":
    main()
