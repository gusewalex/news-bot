import html
import json
import os

import feedparser
import requests
from bs4 import BeautifulSoup

RSS_URL = "https://www.pravda.com.ua/rss/view_mainnews/"
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.environ["CHANNEL"]
STATE_FILE = "posted.json"
MAX_PER_RUN = 5      # максимум новин за один запуск
FIRST_RUN_LIMIT = 3  # скільки новин опублікувати при найпершому запуску
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(links):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(links[-500:], f, ensure_ascii=False, indent=1)


def clean(text):
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def find_image(entry):
    for m in entry.get("media_content", []):
        if m.get("url"):
            return m["url"]
    for e in entry.get("enclosures", []):
        if e.get("type", "").startswith("image") and e.get("href"):
            return e["href"]
    try:
        r = requests.get(entry.link, headers=HEADERS, timeout=15)
        tag = BeautifulSoup(r.text, "html.parser").find("meta", property="og:image")
        if tag and tag.get("content"):
            return tag["content"]
    except Exception as ex:
        print("Не вдалося взяти картинку:", ex)
    return None


def build_text(entry, limit):
    title = html.escape(clean(entry.title))
    head = f"<b>{title}</b>"
    summary = clean(entry.get("summary", ""))
    room = limit - len(head) - 4
    body = ""
    if summary and room > 50:
        s = summary if len(summary) <= room else summary[: room - 1].rsplit(" ", 1)[0] + "…"
        body = "\n\n" + html.escape(s)
    return head + body


def tg(method, **data):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    r = requests.post(url, data=data, timeout=30)
    if not r.ok:
        print("Помилка Telegram:", r.text)
    return r.ok


def send(entry):
    image = find_image(entry)
    if image:
        ok = tg("sendPhoto", chat_id=CHANNEL, photo=image,
                caption=build_text(entry, 1000), parse_mode="HTML")
        if ok:
            return True
    return tg("sendMessage", chat_id=CHANNEL, text=build_text(entry, 3500),
              parse_mode="HTML", disable_web_page_preview=False)


def main():
    feed = feedparser.parse(RSS_URL, agent=HEADERS["User-Agent"])
    entries = list(reversed(feed.entries))  # від старих до нових
    state = load_state()
    first_run = state is None
    posted = state or []

    new = [e for e in entries if e.link not in posted]
    if first_run:
        for e in new[:-FIRST_RUN_LIMIT]:
            posted.append(e.link)
        new = new[-FIRST_RUN_LIMIT:]

    for e in new[:MAX_PER_RUN]:
        if send(e):
            posted.append(e.link)
            print("Опубліковано:", e.title)

    save_state(posted)


main()
