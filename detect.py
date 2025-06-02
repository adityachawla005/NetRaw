import io
import os
import requests
from PIL import Image
from pymongo import MongoClient
import torch
from transformers import pipeline
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client[os.getenv("DB_NAME")]
reddit_posts_collection = db[os.getenv("COLLECTION_NAME")]


weapon_detection_model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
hate_speech_detector = pipeline("text-classification", model="unitary/unbiased-toxic-roberta")

WEAPON_LABELS = [
    'knife', 'scissors', 'gun', 'pistol', 'rifle', 'revolver', 'firearm', 'sword',
    'dagger', 'bat', 'axe', 'machete', 'blade', 'crowbar', 'bow', 'crossbow'
]

def get_weapon_detections_from_image_url(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert('RGB')
    except Exception as e:
        print(f"Could not load image from {image_url}: {e}")
        return []

    detection_results = weapon_detection_model(image)
    detected_weapons = []
    for *box, confidence, class_idx in detection_results.xyxy[0].tolist():
        label = detection_results.names[int(class_idx)]
        if label in WEAPON_LABELS:
            detected_weapons.append({
                "weapon_type": label,
                "confidence_score": confidence,
                "bounding_box": box
            })
    return detected_weapons

def analyze_text_for_hate_speech(text):
    if not text:
        return False, None
    classification_result = hate_speech_detector(text[:512])[0]
    contains_hate_speech = classification_result['label'].upper() in ['TOXIC', 'INSULT', 'THREAT', 'ABUSE']
    return contains_hate_speech, classification_result

def analyze_post_for_objectionable_content(post):
    post_title = post.get('title', '')
    media_urls = post.get('media_urls', [])
    post_link = post.get("url")

    hate_speech_found, hate_speech_details = analyze_text_for_hate_speech(post_title)

    weapons_found = []
    for media_url in media_urls:
        print(f"Analyzing image at {media_url} for weapons...")
        weapons_found.extend(get_weapon_detections_from_image_url(media_url))

    if hate_speech_found and weapons_found:
        return {
            "post_url": post_link,
            "types_of_objectionable_content": ["hate_speech", "weapon"]
        }
    return None

def find_posts_with_both_hate_and_weapons():
    posts_with_media = reddit_posts_collection.find({"media_urls": {"$exists": True, "$ne": []}})
    flagged_posts = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        for flagged_post in executor.map(analyze_post_for_objectionable_content, posts_with_media):
            if flagged_post:
                flagged_posts.append(flagged_post)

    print("Posts flagged with BOTH hate speech and weapon detection:")
    for post_info in flagged_posts:
        print(post_info)

    return flagged_posts

if __name__ == "__main__":
    find_posts_with_both_hate_and_weapons()
