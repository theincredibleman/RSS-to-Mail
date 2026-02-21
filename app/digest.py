import os
import smtplib
import time
import random
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# -----------------------------
# Configuration
# -----------------------------

FEEDS = [
    u.strip()
    for part in os.environ["FEEDS"].strip().splitlines()
    for u in part.split(",")
    if u.strip()
]

LOCAL_TZ = pytz.timezone(os.environ.get("LOCAL_TZ"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}


# -----------------------------
# Utilities
# -----------------------------

def convert_pubdate(entry):
    """Convert RSS pubDate to local timezone."""
    if not getattr(entry, "published_parsed", None):
        return "No publication date available"

    dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))

    if getattr(entry, "published", None):
        try:
            dt = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
        except Exception:
            pass

    return dt.astimezone(LOCAL_TZ).strftime("%A, %d %B %Y %H:%M")


def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


def clean_image_url(url):
    """Only allow absolute HTTPS URLs."""
    if not url:
        return None
    url = url.strip()
    if url in ["?", "#", "none", "null", "undefined", "/"]:
        return None
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    if url.startswith("http://"):
        return None
    return url


def extract_image_from_article(url):
    """Scrape OpenGraph or first <img>."""
    html = fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    def resolve(src):
        if not src:
            return None
        return clean_image_url(urljoin(url, src))

    og = soup.find("meta", property="og:image")
    if og:
        img = resolve(og.get("content"))
        if img:
            return img

    img = soup.find("article img") or soup.find("img")
    if img:
        return resolve(img.get("src"))

    return None


def get_image(entry, link):
    """Try feed images, then scrape."""
    for field in ["media_content", "media_thumbnail"]:
        if field in entry and entry[field]:
            url = clean_image_url(entry[field][0].get("url"))
            if url:
                return url

    if "enclosures" in entry and entry.enclosures:
        url = clean_image_url(entry.enclosures[0].get("href"))
        if url:
            return url

    return extract_image_from_article(link)


# -----------------------------
# HTML Rendering
# -----------------------------

def render_item_html(title, link, pubdate, image_url):
    html = f"""
    <div style="margin-bottom: 30px; font-family: Arial, sans-serif;">
        <h2 style="margin-bottom: 5px;">
            <a href="{link}" style="text-decoration: none; color: #1a0dab;">{title}</a>
        </h2>
        <p style="color: #555; margin-top: 0;">Publication Date: {pubdate}</p>
    """

    if image_url:
        html += f"""
        <div>
            <img src="{image_url}" alt="Article Image"
                 style="max-width: 600px; border-radius: 6px; margin-bottom: 10px;">
        </div>
        """

    return html + "</div>"


def build_email_body(items_html):
    return f"<html><body>{''.join(items_html)}</body></html>"


# -----------------------------
# Email Sending
# -----------------------------

def send_email(html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Daily RSS Digest"
    msg["From"] = f'RSS Digest <{os.environ["SMTP_FROM"]}>'
    msg["To"] = os.environ["EMAIL_TO"]
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        smtp.send_message(msg)


# -----------------------------
# Main Logic
# -----------------------------

def process_feeds():
    all_items = []

    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            ts = (
                time.mktime(entry.published_parsed)
                if getattr(entry, "published_parsed", None)
                else 0
            )
            all_items.append((ts, entry))

    all_items.sort(key=lambda x: x[0], reverse=True)

    items_html = []
    for _, entry in all_items:
        title = entry.title
        link = entry.link
        pubdate = convert_pubdate(entry)
        image_url = get_image(entry, link)

        items_html.append(render_item_html(title, link, pubdate, image_url))
        time.sleep(0.1 + random.random() * 0.1)

    send_email(build_email_body(items_html))


if __name__ == "__main__":
    process_feeds()