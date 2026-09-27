"""
Doğa/Orman Bilgi Botu
----------------------
Claude API ile bir doğa/orman bilgisi üretir, Unsplash'ten lisanslı bir
fotoğraf ya da AI ile üretilmiş bir görsel ekler ve X (Twitter) hesabından
paylaşır.

Gerekli ortam değişkenleri (.env.example dosyasına bak):
  ANTHROPIC_API_KEY
  TWITTER_API_KEY, TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
  UNSPLASH_ACCESS_KEY
  OPENAI_API_KEY        (AI görsel üretimi için)
  CONTENT_LANGUAGE      (opsiyonel, varsayılan "tr")
  IMAGE_MODE            (opsiyonel: "stock" | "ai" | "mixed", varsayılan "mixed")
"""

import base64
import os
import random
import tempfile

import requests
import tweepy
from anthropic import Anthropic

CONTENT_LANGUAGE = os.getenv("CONTENT_LANGUAGE", "tr")
IMAGE_MODE = os.getenv("IMAGE_MODE", "mixed")  # "stock" | "ai" | "mixed"

anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

twitter_client = tweepy.Client(
    consumer_key=os.environ["TWITTER_API_KEY"],
    consumer_secret=os.environ["TWITTER_API_SECRET"],
    access_token=os.environ["TWITTER_ACCESS_TOKEN"],
    access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
)

_auth = tweepy.OAuth1UserHandler(
    os.environ["TWITTER_API_KEY"],
    os.environ["TWITTER_API_SECRET"],
    os.environ["TWITTER_ACCESS_TOKEN"],
    os.environ["TWITTER_ACCESS_SECRET"],
)
twitter_api_v1 = tweepy.API(_auth)  # medya yüklemek için v1.1 lazım


def generate_tweet_text() -> str:
    """Claude API ile doğa/orman hakkında kısa, ilginç bir bilgi üretir."""
    prompt = (
        "Doğa ve orman ekosistemleri hakkında az bilinen, ilginç, doğrulanabilir "
        "bir bilgi paylaş. Türkçe yaz. 240 karakteri geçme, hashtag kullanma, "
        "en fazla 1-2 emoji kullanabilirsin. Sadece tweet metnini döndür, "
        "başka hiçbir açıklama ekleme."
        if CONTENT_LANGUAGE == "tr"
        else "Share a little-known, interesting, verifiable fact about nature "
        "and forest ecosystems. Keep it under 240 characters, no hashtags, "
        "at most 1-2 emojis. Return only the tweet text."
    )
    msg = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def get_stock_image_path(query: str = "forest nature") -> str:
    """Unsplash'ten lisanslı, telif sorunu olmayan bir doğa fotoğrafı çeker."""
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": query, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}"},
        timeout=15,
    )
    resp.raise_for_status()
    image_url = resp.json()["urls"]["regular"]
    img_data = requests.get(image_url, timeout=15).content
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(img_data)
    tmp.close()
    return tmp.name


def get_ai_image_path(prompt_hint: str) -> str:
    """OpenAI görsel üretim API'siyle orijinal bir doğa görseli üretir."""
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={
            "model": "gpt-image-1",
            "prompt": f"Realistic nature photograph style image, forest/nature theme: {prompt_hint}",
            "size": "1024x1024",
        },
        timeout=60,
    )
    resp.raise_for_status()
    b64_data = resp.json()["data"][0]["b64_json"]
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(base64.b64decode(b64_data))
    tmp.close()
    return tmp.name


def get_image_path(tweet_text: str) -> str:
    mode = IMAGE_MODE
    if mode == "mixed":
        mode = random.choice(["stock", "ai"])
    if mode == "ai":
        return get_ai_image_path(tweet_text)
    return get_stock_image_path()


def post_tweet() -> None:
    text = generate_tweet_text()
    image_path = get_image_path(text)
    try:
        media = twitter_api_v1.media_upload(image_path)
        twitter_client.create_tweet(text=text, media_ids=[media.media_id])
        print("Paylaşıldı:", text)
    finally:
        os.remove(image_path)


if __name__ == "__main__":
    post_tweet()
