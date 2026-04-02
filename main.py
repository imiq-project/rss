from flask import Flask, Response
from feedgen.feed import FeedGenerator
from apscheduler.schedulers.background import BackgroundScheduler
from linkedin_scraper import BrowserManager, CompanyPostsScraper, login_with_credentials
import asyncio
import os


LINKEDIN_EMAIL = os.environ["LINKEDIN_EMAIL"]
LINKEDIN_PASSWORD = os.environ["LINKEDIN_PASSWORD"]
SESSION_FILE = "session.json"
LINKEDIN_URL = "https://de.linkedin.com/company/imiq-intelligenter-mobilitätsraum-im-quartier/posts/"

cached_feed = ""


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
    print("Updating RSS feed...")
    asyncio.run(scrape_company_posts())
    print("Done.")


app = Flask(__name__)


@app.route("/feed.xml")
def feed():
    return Response(cached_feed, mimetype="application/xml")


if __name__ == "__main__":

    if not os.path.exists(SESSION_FILE):
        print(f"{SESSION_FILE} not found, logging in as f{LINKEDIN_EMAIL}...")
        asyncio.run(login())
        print("Done.")

    # Schedule daily update (06:00)
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_feed, "cron", hour=6, minute=0)
    scheduler.start()

    # Generate once on startup
    update_feed()

    # Start server
    app.run(host="0.0.0.0", port=8000)
