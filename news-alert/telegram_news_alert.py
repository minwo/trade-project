import difflib
import feedparser
import html
import json
import os
import pathlib
import re
import urllib.parse

import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

BASE_DIR = pathlib.Path(__file__).parent
KEYWORDS_FILE = BASE_DIR / "keywords.txt"
TRIGGERS_FILE = BASE_DIR / "importance_triggers.txt"
SEEN_FILE = BASE_DIR / "seen_titles.json"
SEEN_LIMIT = 3000
DUPLICATE_SIMILARITY = 0.82


def load_lines(path):
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def load_keywords():
    return load_lines(KEYWORDS_FILE)


def load_triggers():
    return load_lines(TRIGGERS_FILE)


def is_important(title, triggers):
    return any(trigger in title for trigger in triggers)


def load_seen():
    if SEEN_FILE.exists():
        return list(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return []


def save_seen(seen):
    trimmed = seen[-SEEN_LIMIT:]
    SEEN_FILE.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")


def send_telegram(text):
    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": False},
        timeout=10,
    )
    resp.raise_for_status()


def clean_html(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def normalize_title(title):
    t = re.sub(r"\s+", " ", title).strip()
    t = re.sub(r"^(\[[^\]]{1,10}\]\s*)+", "", t)  # 앞의 [속보][단독][영상] 등 태그 제거
    t = re.sub(r"\s*[-|ㅣ·—–_]\s*[^-|ㅣ·—–_]{1,20}$", "", t)  # 끝의 " - 언론사명" 류 제거
    t = re.sub(r"[\"'“”‘’…\.]", "", t)
    return t.lower()


def is_duplicate(norm_title, seen_titles):
    if norm_title in seen_titles:
        return True
    return any(
        difflib.SequenceMatcher(None, norm_title, s).ratio() >= DUPLICATE_SIMILARITY
        for s in seen_titles
    )


def fetch_google_news(keyword):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    results = [(entry.title, entry.link, "Google") for entry in feed.entries[:10]]
    print(f"  google[{keyword}]: {len(results)}건")
    return results


def fetch_naver_news(keyword):
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        print(f"  naver[{keyword}]: skipped (NAVER_CLIENT_ID/SECRET not set)")
        return []
    resp = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": keyword, "display": 10, "sort": "date"},
        headers={
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    results = [
        (clean_html(item["title"]), item["originallink"] or item["link"], "Naver")
        for item in items
    ]
    print(f"  naver[{keyword}]: {len(results)}건")
    return results


def gather_articles(keywords):
    for keyword in keywords:
        for title, link, source in fetch_google_news(keyword) + fetch_naver_news(keyword):
            yield keyword, title, link, source


def main():
    print(f"naver configured: {bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)}")
    keywords = load_keywords()
    triggers = load_triggers()
    seen = load_seen()
    sent_this_run = []
    new_count = 0
    for keyword, title, link, source in gather_articles(keywords):
        key = normalize_title(title)
        if is_duplicate(key, seen) or is_duplicate(key, sent_this_run):
            continue
        if not is_important(title, triggers):
            continue
        send_telegram(f"[{keyword}][{source}] {title}\n{link}")
        seen.append(key)
        sent_this_run.append(key)
        new_count += 1
    save_seen(seen)
    print(f"checked {len(keywords)} keywords, sent {new_count} new articles")


if __name__ == "__main__":
    main()
