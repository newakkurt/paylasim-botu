import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime
import requests
import telebot

# --- TWIKIT VE PATCH ---
try:
    import base64
    import twikit.x_client_transaction.transaction as tx

    _INDICES_RE = re.compile(r'\(\w\[(\d{1,2})\],\s*16\)')
    _ONDEMAND_URL_RE = re.compile(
        r'https://abs\.twimg\.com/responsive-web/client-web/ondemand\.s\.[a-zA-Z0-9]+\.js'
    )
    _ONDEMAND_ALT_RE = re.compile(
        r'https://abs\.twimg\.com/responsive-web/client-web/[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+\.js'
    )
    _ONDEMAND_HASH_RE = re.compile(r'''['"]ondemand\.s['"]\s*:\s*['"](\w+)['"]''')

    async def _patched_get_indices(self, home_page_response, session, headers):
        page = str(home_page_response)
        if len(page) < 1000 and getattr(self, "home_page_response", None) is not None:
            page = str(self.home_page_response)

        js_urls = []
        m = _ONDEMAND_URL_RE.search(page)
        if m:
            js_urls.append(m.group(0))
        
        h = _ONDEMAND_HASH_RE.search(page)
        if h:
            js_urls.append(f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{h.group(1)}a.js")

        all_matches = _ONDEMAND_ALT_RE.findall(page)
        for url in all_matches[:5]:
            if url not in js_urls:
                js_urls.append(url)

        for js_url in js_urls:
            try:
                resp = await session.request(method="GET", url=js_url, headers=headers)
                nums = [int(x) for x in _INDICES_RE.findall(str(resp.text))]
                if len(nums) >= 2:
                    return nums[0], nums[1:]
            except Exception:
                continue

        return 0, [3, 8, 12, 19, 25, 31]

    tx.ClientTransaction.get_indices = _patched_get_indices
except Exception as e:
    print(f"Twikit patch hatası: {e}")

from twikit import Client

# --- ENV VARIABLES ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
X_COOKIES_JSON = os.getenv("X_COOKIES_JSON")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None

# --- HASHTAG GARANTİSİ (EN AZ 5 HASHTAG) ---
DEFAULT_HASHTAGS = ["#Nature", "#Wildlife", "#Earth", "#NaturePhotography", "#Environment"]

def ensure_hashtags(text: str) -> str:
    found_tags = re.findall(r'#\w+', text)
    if len(found_tags) < 5:
        missing = [tag for tag in DEFAULT_HASHTAGS if tag not in found_tags]
        text += " " + " ".join(missing[:5 - len(found_tags)])
    return text.strip()

# --- COOKIE FORMAT DÖNÜŞTÜRÜCÜ ---
def parse_cookies_data(raw_cookies_json):
    if not raw_cookies_json:
        return None
    try:
        data = json.loads(raw_cookies_json)
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            cookie_dict = {}
            for item in data:
                if isinstance(item, dict) and 'name' in item and 'value' in item:
                    cookie_dict[item['name']] = item['value']
            return cookie_dict
    except Exception as e:
        print(f"⚠️ Cookie parse hatası: {e}")
    return None

# --- YEDEK BİLGİ HAVUZU ---
FALLBACK_NOTES = [
    "Did you know? Trees in a forest can communicate and share nutrients through an underground fungal network. #NatureFacts #ForestLife #Trees #MotherNature #EcoSystem",
    "Bananas are naturally slightly radioactive because they contain high levels of potassium. #Science #Nature #ScienceFacts #Biology #NatureWonders",
    "Honey never spoils. Archeologists have found 3,000-year-old honey in ancient Egyptian tombs. #NatureMagic #Honey #History #AncientEgypt #FoodFacts",
    "A single full-grown oak tree can absorb up to 50 gallons of water per day. #Trees #Environment #Forests #SaveTrees #GreenPlanet",
    "Clouds look light and fluffy, but an average cumulus cloud weighs about 1.1 million pounds! #Weather #Nature #Atmosphere #Sky #NatureFacts",
] + [f"Nature Fact #{i}: Ecosystem diversity supports millions of interconnected species across climate zones. #Nature #Ecology #Biodiversity #Earth #Wildlife" for i in range(6, 301)]

def notify_telegram(message_text):
    if bot and TELEGRAM_CHAT_ID:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Telegram bildirim hatası: {e}")

def get_season_context():
    now = datetime.now()
    month, day = now.month, now.day
    if month in [12, 1, 2]:
        season = "Winter (serene snow, calm forests)"
    elif month in [3, 4, 5]:
        season = "Spring (fresh flowers, rebirth)"
    elif month in [6, 7, 8]:
        season = "Summer (golden sunlight, warm oceans)"
    else:
        season = "Autumn (golden leaves, misty mornings)"
    return season

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

# --- POST TO X ---
async def post_to_x(text, media_path=None):
    client = Client('en-US')
    cookies = parse_cookies_data(X_COOKIES_JSON)

    if not cookies:
        return False, "Cookies parse edilemedi."

    try:
        client.set_cookies(cookies)
    except Exception as e:
        return False, f"Cookie set hatası: {e}"

    media_ids = []
    if media_path and os.path.exists(media_path):
        try:
            m_id = await client.upload_media(media_path)
            if m_id:
                media_ids.append(m_id)
        except Exception as e:
            print(f"Görsel yükleme atlandı: {e}")

    try:
        tweet = await client.create_tweet(text=text, media_ids=media_ids if media_ids else None)
        print(f"✅ Tweet atıldı! ID: {tweet.id}")
    except Exception as e:
        # Hatanın gerçek nedenini döndür
        return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
        except Exception:
            pass

    return True, "OK"

def run_job():
    now_hour = datetime.now().hour

    if 7 <= now_hour < 9:
        text = get_weather_info()
        img = fetch_hd_image("morning sunrise nature")
        success, reason = asyncio.run(post_to_x(text, img))
        if success:
            notify_telegram(f"☀️ **Sabah Hava Durumu Paylaşıldı!**\n\n_{text}_")
        else:
            notify_telegram(f"❌ **Hava Durumu Hata:** `{reason}`")

    else:
        ctx = get_season_context()
        prompt = f"Write a beautiful English tweet about nature. Context: {ctx}. Max 180 chars. Include at least 5 relevant hashtags."
        text = generate_ai_text(prompt)
        img = fetch_hd_image("scenic nature landscape")
        success, reason = asyncio.run(post_to_x(text, img))
        if success:
            notify_telegram(f"📸 **Görsel İçerik Paylaşıldı!**\n\n_{text}_")
        else:
            notify_telegram(f"❌ **Paylaşım Hatası:** `{reason}`")

if __name__ == "__main__":
    run_job()
