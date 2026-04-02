from flask import Flask, Response
from feedgen.feed import FeedGenerator
from apscheduler.schedulers.background import BackgroundScheduler
from linkedin_scraper import BrowserManager, CompanyPostsScraper, login_with_credentials
import asyncio
import os
import time


LINKEDIN_EMAIL = os.environ["LINKEDIN_EMAIL"]
LINKEDIN_PASSWORD = os.environ["LINKEDIN_PASSWORD"]
SESSION_FILE = "/data/session.json"
LAST_FEED_FILE = "/data/feed.xml"

LINKEDIN_URL = "https://de.linkedin.com/company/imiq-intelligenter-mobilitätsraum-im-quartier/posts/"

cached_feed: bytes = b""


async def login():
    async with BrowserManager(headless=True) as browser:
        # Login with credentials
        await login_with_credentials(
            browser.page,
            LINKEDIN_EMAIL,
            LINKEDIN_PASSWORD,
        )
        # Save session for reuse
        await browser.save_session(SESSION_FILE)


async def scrape_company_posts():
    async with BrowserManager(headless=True) as browser:
        await browser.load_session(SESSION_FILE)
        scraper = CompanyPostsScraper(browser.page)
        posts = await scraper.scrape(LINKEDIN_URL, limit=10)

    fg = FeedGenerator()
    fg.title("IMIQ LinkedIn Feed")
    fg.link(href=LINKEDIN_URL)
    fg.description("Daily LinkedIn posts")

    for post in posts:
        fe = fg.add_entry()
        fe.title(f"{post.posted_date} ago")
        fe.description(post.text)
        fe.link(href=post.linkedin_url)
        for img_url in post.image_urls:
            fe.enclosure(url=img_url, type="image/jpeg", length=0)
        # fe.pubDate(datetime.datetime.now(datetime.timezone.utc))

    global cached_feed
    cached_feed = fg.rss_str(pretty=True)


def update_feed():
    global cached_feed

    print("Updating RSS feed...")
    try:
        asyncio.run(scrape_company_posts())
    except Exception as e:
        print(f"Failed: {e}")
        return

    with open(LAST_FEED_FILE, "w") as f:
        f.write(cached_feed.decode())

    print("Done.")

def load_last_feed():
    global cached_feed
    print("Loading last feed...")
    try:
        with open(LAST_FEED_FILE) as f:
            cached_feed = f.read().encode()
        print(f"Done (len={len(cached_feed)})")
    except Exception as e:
        print(f"Cannot load last feed: {e}")

app = Flask(__name__)


@app.route("/feed.xml")
def feed():
    return Response(cached_feed, mimetype="application/xml")


if __name__ == "__main__":

    load_last_feed()

    if not os.path.exists(SESSION_FILE):
        print(f"{SESSION_FILE} not found, logging in as f{LINKEDIN_EMAIL}...")
        try:
            asyncio.run(login())
        except Exception as e:
            print(f"Login failed: {e}")
            while True:
                time.sleep(1)

        print("Done.")

    # Schedule daily update (06:00)
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_feed, "cron", hour=6, minute=0)
    scheduler.start()

    # Generate once on startup
    update_feed()

    # Start server
    app.run(host="0.0.0.0", port=8000)
