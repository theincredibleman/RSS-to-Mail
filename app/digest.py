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


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

# FEEDS must be set as an environment variable named `FEEDS`.
# Accepts comma- or newline-separated URLs.
_feeds_env = os.environ["FEEDS"].strip()
FEEDS = [u.strip() for part in _feeds_env.splitlines() for u in part.split(",") if u.strip()]

LOCAL_TZ = pytz.timezone("Europe/Amsterdam")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def convert_pubdate(entry) -> str:
    """Convert RSS pubDate to local timezone and format nicely."""
    if not hasattr(entry, "published_parsed") or entry.published_parsed is None:
        return "No publication date available"

    # Base timestamp
    dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))

    # Try parsing published string if available
    if hasattr(entry, "published"):
        try:
            dt = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
        except Exception:
            pass

    return dt.astimezone(LOCAL_TZ).strftime("%A, %d %B %Y %H:%M")


def fetch_page(url: str, retries: int = 3) -> str | None:
    """Fetch a webpage with retry logic and browser headers."""
    for _ in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass

        time.sleep(0.5 + random.random() * 0.5)

    return None


def extract_image_from_article(url: str) -> str | None:
    """Extract the main image from an article."""
    html = fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Prefer OpenGraph image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]

    # Try article body
    article = soup.find("article")
    if article:
        img = article.find("img")
        if img and img.get("src"):
            return img["src"]

    # Fallback: any image
    img = soup.find("img")
    return img["src"] if img and img.get("src") else None


# -------------------------------------------------------------------
# HTML Rendering
# -------------------------------------------------------------------

def render_item_html(title: str, link: str, pubdate: str, image_url: str | None) -> str:
    """Render a single RSS item into HTML."""
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

    html += "</div>"
    return html


def build_email_body(items_html: list[str]) -> str:
    """Wrap all items into a full HTML email body."""
    return f"""
    <html>
    <body>
    {''.join(items_html)}
    </body>
    </html>
    """


# -------------------------------------------------------------------
# Email Sending
# -------------------------------------------------------------------

def send_email(html_body: str) -> None:
    """Send the final HTML email."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Daily BleepingComputer RSS Digest"
    msg["From"] = f'BleepingComputer RSS Digest <{os.environ["SMTP_FROM"]}>'
    msg["To"] = os.environ["EMAIL_TO"]
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        smtp.send_message(msg)


# -------------------------------------------------------------------
# Main Logic
# -------------------------------------------------------------------

def process_feeds() -> None:
    items_html = []

    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)

        for entry in parsed.entries:
            title = entry.title
            link = entry.link
            pubdate = convert_pubdate(entry)

            # Prefer media content from RSS
            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")
            elif "media_thumbnail" in entry and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get("url")

            # Fallback: scrape article
            if not image_url:
                image_url = extract_image_from_article(link)

            items_html.append(render_item_html(title, link, pubdate, image_url))

            time.sleep(0.15 + random.random() * 0.15)

    body_html = build_email_body(items_html)
    send_email(body_html)


if __name__ == "__main__":
    process_feeds()
