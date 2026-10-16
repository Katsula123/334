"""Collect public RSS headlines for a static GitHub Pages news index.

Each record keeps the original article URL and, when available, an image
referenced by that exact article's RSS item or Open Graph metadata.
"""
import calendar
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / "news.json"
NOW = datetime.now(timezone.utc)
HEADERS = {"User-Agent": "TaiwanMotorDaily/1.0 (+personal non-commercial RSS reader; GitHub Pages)"}
FEEDS = [
    ("Mobile01", "https://www.mobile01.com/rss/news.xml"),
    ("中央社", "https://feeds.feedburner.com/rsscna/finance"),
    ("中央社", "https://feeds.feedburner.com/rsscna/lifehealth"),
    ("自由時報", "https://news.ltn.com.tw/rss/business.xml"),
    ("自由時報", "https://news.ltn.com.tw/rss/life.xml"),
    ("交通部公路局", "https://www.thb.gov.tw/OpenData.aspx?SN=14F103987102091C"),
]

POLICY = re.compile(r"交通法規|道路交通管理|交通新制|交通違規|道路安全|新制|施行|修法|罰鍰|罰單|開罰|裁罰|違規記點|換照|考照|駕照|驗車|監理|牌照|酒駕|停讓|行人|汽燃費|公路養管費|交通部.+(公告|新制)", re.I)
MOTO = re.compile(r"機車|重機|二輪|速克達|電動機車|騎士|摩托|Gogoro|KYMCO|SYM|三陽|光陽|Vespa|Ducati|MotoGP|Yamaha\s+(?:YZF|MT|XMAX|NMAX)", re.I)
CAR = re.compile(r"汽車|車款|新車|車型|改款|車廠|車展|休旅|SUV|轎車|房車|跑車|皮卡|油電|純電|電動車|充電樁|自駕車|車價|車市|試駕|國產車|Toyota|Lexus|Honda|Nissan|Mazda|Hyundai|Kia|Volkswagen|Tesla|Mercedes|Porsche|Subaru|Mitsubishi|Volvo|Ford|BMW|Audi|Škoda|ŠKODA|Suzuki|BYD|RAV4|CR-V|HR-V|Civic|Corolla|Altis|Model\s+[3YXS]", re.I)
ACCIDENT = re.compile(r"車禍|肇事|撞死|撞傷|火燒車|連環撞|車輛翻覆|交通事故", re.I)
LAW_CHANGE = re.compile(r"修法|新制|規定|修正|法規|違規|酒駕|罰鍰|停讓", re.I)
BAD_IMAGE = re.compile(r"logo|icon|favicon|avatar|placeholder|default|loading|pixel|sprite", re.I)


def http_url(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ("http", "https") and parsed.netloc else ""
    except ValueError:
        return ""


def short_text(value, limit=110):
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:limit].rstrip("，。；、 ") + ("…" if len(text) > limit else "")


def get_date(entry):
    time_value = entry.get("published_parsed") or entry.get("updated_parsed")
    if not time_value:
        return None
    try:
        parsed = datetime.fromtimestamp(calendar.timegm(time_value), tz=timezone.utc)
        if parsed > NOW + timedelta(days=1) or parsed < NOW - timedelta(days=45):
            return None
        return parsed
    except (ValueError, OverflowError, TypeError):
        return None


def classify(title, source):
    if ACCIDENT.search(title) and not LAW_CHANGE.search(title):
        return None
    if POLICY.search(title):
        return "交通法規"
    if source == "交通部公路局":
        return None  # Exclude roadworks, tenders, and unrelated announcements.
    if MOTO.search(title):
        return "機車"
    if CAR.search(title):
        return "汽車"
    return None


def rss_image(entry):
    for media_key in ("media_content", "media_thumbnail", "enclosures"):
        for media in entry.get(media_key, []):
            link = http_url(media.get("url", ""))
            if link and not BAD_IMAGE.search(urlsplit(link).path):
                return link
    html = entry.get("summary", "") or entry.get("description", "")
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img", src=True):
        link = http_url(img["src"])
        if link and not BAD_IMAGE.search(urlsplit(link).path):
            return link
    return ""


def og_image(article_url):
    """Look only at image metadata on the matching article, never search a vehicle by name."""
    try:
        response = requests.get(article_url, headers=HEADERS, timeout=(5, 9))
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", "").lower():
            return ""
        soup = BeautifulSoup(response.text[:750000], "html.parser")
        for key in ("og:image", "twitter:image"):
            tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                link = http_url(urljoin(response.url, tag["content"]))
                if link and not BAD_IMAGE.search(urlsplit(link).path):
                    return link
    except requests.RequestException as exc:
        print(f"Image lookup skipped: {article_url} ({exc})")
    return ""


def read_feed(source, url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=(7, 18))
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if not feed.entries:
            print(f"WARNING: empty or unavailable feed: {source} {url}")
            return []
        out = []
        for entry in feed.entries:
            title = short_text(entry.get("title", ""), 180)
            link = http_url(entry.get("link", ""))
            published = get_date(entry)
            kind = classify(title, source)
            if not title or not link or not published or not kind:
                continue
            out.append({
                "title": title,
                "link": link,
                "category": kind,
                "source": source,
                "published": published.astimezone(timezone(timedelta(hours=8))).strftime("%Y/%m/%d"),
                "sort_at": published.isoformat(),
                "summary": short_text(entry.get("summary", ""), 115),
                "image": rss_image(entry),
            })
        print(f"{source}: {len(out)} matching articles")
        return out
    except requests.RequestException as exc:
        print(f"WARNING: RSS fetch failed for {source}: {exc}")
        return []


def build():
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for collection in pool.map(lambda pair: read_feed(*pair), FEEDS):
            results.extend(collection)
    unique = {}
    for item in sorted(results, key=lambda x: x["sort_at"], reverse=True):
        normalized = re.sub(r"[\W_]+", "", item["title"].casefold())
        if normalized not in unique:
            unique[normalized] = item
    ordered = list(unique.values())
    # Keep some motorcycle and policy reporting visible, even on car-heavy days.
    chosen = []
    seen = set()
    for kind in ("汽車", "機車", "交通法規"):
        for item in [x for x in ordered if x["category"] == kind][:3]:
            if item["link"] not in seen:
                chosen.append(item)
                seen.add(item["link"])
    for item in ordered:
        if len(chosen) >= 36:
            break
        if item["link"] not in seen:
            chosen.append(item)
            seen.add(item["link"])
    chosen = sorted(chosen, key=lambda x: x["sort_at"], reverse=True)[:36]
    if not chosen:
        print("ERROR: no usable news. Keep the previous Pages deployment intact.", file=sys.stderr)
        raise SystemExit(1)
    # Resolve thumbnails concurrently; all pictures belong to the exact linked article.
    with ThreadPoolExecutor(max_workers=6) as pool:
        missing = [item for item in chosen if not item["image"]]
        images = pool.map(lambda item: og_image(item["link"]), missing)
        for item, image in zip(missing, images):
            item["image"] = image
    for item in chosen:
        item.pop("sort_at", None)
    data = {"updated_at": NOW.isoformat(timespec="seconds"), "items": chosen}
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(chosen)} articles to {OUTPUT}")


if __name__ == "__main__":
    build()
