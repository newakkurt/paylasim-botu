import os
import random
import re
from datetime import datetime
import requests
import telebot
import tweepy

# --- ENV VARIABLES ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None

# --- HASHTAG GARANTİSİ ---
DEFAULT_HASHTAGS = ["#Nature", "#Wildlife", "#Earth", "#NaturePhotography", "#Environment"]

def ensure_hashtags(text: str) -> str:
    found_tags = re.findall(r'#\w+', text)
    if len(found_tags) < 5:
        missing = [tag for tag in DEFAULT_HASHTAGS if tag not in found_tags]
        text += " " + " ".join(missing[:5 - len(found_tags)])
    return text.strip()

# --- YEDEK İÇERİK HAVUZU ---
FALLBACK_NOTES = [
    "Did you know? Trees in a forest can communicate and share nutrients through an underground fungal network. #NatureFacts #ForestLife #Trees #MotherNature #EcoSystem",
    "Bananas are naturally slightly radioactive because they contain high levels of potassium. #Science #Nature #ScienceFacts #Biology #NatureWonders",
    "Honey never spoils. Archeologists have found 3,000-year-old honey in ancient Egyptian tombs. #NatureMagic #Honey #History #AncientEgypt #FoodFacts",
    "A single full-grown oak tree can absorb up to 50 gallons of water per day. #Trees #Environment #Forests #SaveTrees #GreenPlanet",
    "Clouds look light and fluffy, but an average cumulus cloud weighs about 1.1 million pounds! #Weather #Nature #Atmosphere #Sky #NatureFacts"
]

def notify_telegram(message_text):
    if bot and TELEGRAM_CHAT_ID:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Telegram bildirim hatası: {e}")

def get_season_context():
    now = datetime.now()
    month = now.month
    if month in [12, 1, 2]:
        return "Winter (serene snow, calm forests)"
    elif month in [3, 4, 5]:
        return "Spring (fresh flowers, rebirth)"
    elif month in [6, 7, 8]:
        return "Summer (golden sunlight, warm oceans)"
    else:
        return "Autumn (golden leaves, misty mornings)"

def generate_ai_text(prompt: str) -> str:
    generated = None
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if res.status_code == 200:
                generated = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            print(f"Gemini Hatası: {e}")

    if not generated and GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                generated = res.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Groq Hatası: {e}")

    if not generated:
        generated = random.choice(FALLBACK_NOTES)

    return ensure_hashtags(generated)

def fetch_hd_image(query: str = "nature landscape") -> str:
    file_path = "temp_image.jpg"
    if UNSPLASH_ACCESS_KEY:
        try:
            url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                img_url = res.json()['urls']['regular']
                with open(file_path, 'wb') as f:
                    f.write(requests.get(img_url, timeout=15).content)
                return file_path
        except Exception as e:
            print(f"Unsplash hatası: {e}")

    if PEXELS_API_KEY:
        try:
            headers = {"Authorization": PEXELS_API_KEY}
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=10"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                photos = res.json().get('photos', [])
                if photos:
                    img_url = random.choice(photos)['src']['large2x']
                    with open(file_path, 'wb') as f:
                        f.write(requests.get(img_url, timeout=15).content)
                    return file_path
        except Exception as e:
            print(f"Pexels hatası: {e}")

    return None

def get_weather_info():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=41.0082&longitude=28.9784&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Europe%2FIstanbul"
        res = requests.get(url, timeout=10).json()
        max_t = res['daily']['temperature_2m_max'][0]
        min_t = res['daily']['temperature_2m_min'][0]
        text = f"Good morning! Today in Istanbul: High of {max_t}°C, Low of {min_t}°C. Embrace nature! ☀️🌿 #Weather #Nature #Istanbul #GoodMorning #NatureVibes"
    except Exception:
        text = "Good morning! Wishing you a peaceful and nature-filled day ahead! 🌿 #Nature #MorningVibes #Peaceful #GreenPlanet #Earth"
    return ensure_hashtags(text)

# --- TWITTER OFFICIAL API V2 (TWEEPY) ---
def post_to_x(text, media_path=None):
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        return False, "Twitter API Key/Secret bilgileri eksik."

    try:
        # v1.1 Client (Medya Yükleme İçin)
        auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)

        # v2 Client (Tweet Paylaşımı İçin)
        client_v2 = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET
        )

        media_ids = []
        if media_path and os.path.exists(media_path):
            try:
                media = api_v1.media_upload(filename=media_path)
                media_ids.append(media.media_id)
            except Exception as e:
                print(f"Görsel yükleme atlandı: {e}")

        response = client_v2.create_tweet(text=text, media_ids=media_ids if media_ids else None)
        print(f"✅ Tweet atıldı! ID: {response.data['id']}")

        if media_path and os.path.exists(media_path):
            os.remove(media_path)

        return True, "OK"

    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"

def run_job():
    now_hour = datetime.now().hour

    if 7 <= now_hour < 9:
        text = get_weather_info()
        img = fetch_hd_image("morning sunrise nature")
        success, reason = asyncio_run = post_to_x(text, img)
        if success:
            notify_telegram(f"☀️ **Sabah Hava Durumu Paylaşıldı!**\n\n_{text}_")
        else:
            notify_telegram(f"❌ **Hava Durumu Hata:** `{reason}`")
    else:
        ctx = get_season_context()
        prompt = f"Write a beautiful English tweet about nature. Context: {ctx}. Max 180 chars. Include at least 5 relevant hashtags."
        text = generate_ai_text(prompt)
        img = fetch_hd_image("scenic nature landscape")
        success, reason = post_to_x(text, img)
        if success:
            notify_telegram(f"📸 **Görsel İçerik Paylaşıldı!**\n\n_{text}_")
        else:
            notify_telegram(f"❌ **Paylaşım Hatası:** `{reason}`")

if __name__ == "__main__":
    run_job()
