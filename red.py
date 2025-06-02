from pymongo import MongoClient
from datetime import datetime, timezone
import praw
from dotenv import load_dotenv
import os

load_dotenv()

SEARCH_KEYWORDS = ["gun", "firearm", "knife", "sword", "weapon", "guns", "knives", "firearms", "blade", "blades"]

mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME")]

def extract_reddit_media_urls(post):
    media_urls = []
    if getattr(post, "is_gallery", False):
        media_metadata = getattr(post, "media_metadata", {})
        for media_info in media_metadata.values():
            if media_info.get("status") == "valid":
                p = media_info.get("p", [])
                if p:
                    media_urls.append(p[-1].get("u").replace("&amp;", "&"))
                else:
                    media_urls.append(media_info.get("s", {}).get("u", "").replace("&amp;", "&"))
    elif getattr(post, "media", None) and "reddit_video" in post.media:
        video_url = post.media["reddit_video"].get("fallback_url")
        if video_url:
            media_urls.append(video_url)
    elif getattr(post, "preview", None):
        for image in post.preview.get("images", []):
            url = image.get("source", {}).get("url")
            if url:
                media_urls.append(url.replace("&amp;", "&"))
    elif post.url and post.url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".mp4")):
        media_urls.append(post.url)
    return media_urls

def build_search_query(keywords):
    return " OR ".join(keywords)

def main():
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT")
    )

    subreddit = reddit.subreddit("all")
    search_query = build_search_query(SEARCH_KEYWORDS)
    today_utc = datetime.now(timezone.utc).date()

    for post in subreddit.search(search_query, limit=100, sort="new"):
        post_date = datetime.fromtimestamp(post.created_utc, timezone.utc).date()
        if post_date == today_utc:
            media_urls = extract_reddit_media_urls(post)
            data = {
                "title": post.title,
                "author": str(post.author),
                "subreddit": str(post.subreddit),
                "url": f"https://reddit.com{post.permalink}",
                "media_urls": media_urls,
                "created_utc": post.created_utc,
                "timestamp": datetime.utcnow()
            }
            collection.insert_one(data)
            print(f"Saved post: {post.title}")

if __name__ == "__main__":
    main()
