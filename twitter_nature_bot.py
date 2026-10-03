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

# --- TWIKIT KEY_BYTE DÜZELTME YAMASI (GÜNCEL) ---
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

        # Alternatif JS bağlamları
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

        # Varsayılan fallback indeksleri (X güncellemelerinde çökmemesi için)
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

# --- COOKIE FORMAT DÖNÜŞTÜRÜCÜ ---
def parse_cookies_data(raw_cookies_json):
    if not raw_cookies_json:
        return None
    
    try:
        data = json.loads(raw_cookies_json)
        if isinstance(data, list):
            cookie_dict = {}
            for item in data:
                if isinstance(item, dict) and 'name' in item and 'value' in item:
                    cookie_dict[item['name']] = item['value']
            return cookie_dict
        elif isinstance(data, dict):
            return data
    except Exception as e:
        print(f"⚠️ Cookie parse hatası: {e}")
    
    return None

# --- 300 YEDEK BİLGİ HAVUZU ---
FALLBACK_NOTES = [
    "Did you know? Trees in a forest can communicate and share nutrients through an underground fungal network often called the 'Wood Wide Web'. #NatureFacts #ForestLife",
    "Bananas are naturally slightly radioactive because they contain high levels of potassium, specifically the isotope potassium-40. #Science #Nature",
    "Honey never spoils. Archeologists have found 3,000-year-old honey in ancient Egyptian tombs that is still completely edible! #NatureMagic",
    "A single full-grown oak tree can absorb up to 50 gallons of water per day and produce enough oxygen for several people. #Trees #Environment",
    "Clouds look light and fluffy, but an average cumulus cloud weighs about 1.1 million pounds (500,000 kg)! #Weather #Nature",
    "Octopuses have three hearts and blue blood. Two hearts pump blood to the gills, while the third pumps it to the rest of the body. #OceanLife",
    "The Amazon Rainforest generates more than 20% of the Earth's oxygen supply, making it crucial for global ecology. #Rainforest #GreenPlanet",
    "Sunflowers can be used to clean up radioactive waste. Their roots absorb toxins and heavy metals from contaminated soil. #Botany #EcoFriendly",
    "Lightning strikes the Earth approximately 8 million times every single day. #NaturePower #Atmosphere",
    "The smell of freshly cut grass is actually a plant distress call signal released to warn neighboring plants of danger. #PlantScience",
] + [f"Nature Fact #{i}: The diversity of ecosystems on Earth supports millions of interconnected species, creating balance across climate zones. #Nature" for i in range(11, 301)]

# --- TELEGRAM BİLDİRİMİ ---
def notify_telegram(message_text):
    if bot and TELEGRAM_CHAT_ID:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Telegram bildirim hatası: {e}")

# --- MEVSİM VEYA ÖZEL GÜN TESPİTİ ---
def get_season_context():
    now = datetime.now()
    month, day = now.month, now.day
    if month in [12, 1, 2]:
        season = "Winter (serene snow, calm forests, cold atmosphere, inner peace)"
    elif month in [3, 4, 5]:
        season = "Spring (fresh flowers blooming, vibrant leaves, rebirth, greenery)"
    elif month in [6, 7, 8]:
        season = "Summer (golden sunlight, warm oceans, lush green nature)"
    else:
        season = "Autumn (golden leaves falling, misty crisp mornings, cozy vibes)"

    special = ""
    if month == 4 and day == 22:
        special = "Today is Earth Day! Emphasize environmental protection."
    elif month == 6 and day == 5:
        special = "Today is World Environment Day!"

    return f"{season}. {special}".strip()

# --- YEDEKLİ AI METİN ÜRETİCİSİ ---
def generate_ai_text(prompt: str) -> str:
    # 1. Gemini
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            print(f"⚠️ Gemini Hatası: {e}")

    # 2. Groq
    if GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"⚠️ Groq Hatası: {e}")

    # 3. OpenRouter
    if OPENROUTER_API_KEY:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "meta-llama/llama-3.1-8b-instruct:free", "messages": [{"role": "user", "content": prompt}]}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"⚠️️ OpenRouter Hatası: {e}")

    # 4. Fallback
    print("🚨 AI motorları yanıt vermedi. Yedek bilgi notundan seçiliyor...")
    return random.choice(FALLBACK_NOTES)

# --- HD GÖRSEL ÇEKME ---
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

# --- HAVA DURUMU ALMA ---
def get_weather_info():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=41.0082&longitude=28.9784&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Europe%2FIstanbul"
        res = requests.get(url, timeout=10).json()
        max_t = res['daily']['temperature_2m_max'][0]
        min_t = res['daily']['temperature_2m_min'][0]
        return f"Good morning! Today in Istanbul: High of {max_t}°C, Low of {min_t}°C. Embrace the beauty of nature today! ☀️🌿 #Weather #Nature"
    except Exception:
        return "Good morning! Wishing you a peaceful and nature-filled day ahead! 🌿 #Nature #MorningVibes"

# --- CORE TWEET PAYLAŞIM MOTORU ---
async def post_to_x(text, media_path=None):
    client = Client('en-US')
    cookies = parse_cookies_data(X_COOKIES_JSON)

    if not cookies:
        print("❌ X_COOKIES_JSON eksik veya çözümlenemedi.")
        return None

    try:
        client.set_cookies(cookies)
    except Exception as e:
        print(f"❌ Çerezler atanırken hata oluştu: {e}")
        return None

    media_ids = []
    if media_path and os.path.exists(media_path):
        try:
            m_id = await client.upload_media(media_path)
            if m_id:
                media_ids.append(m_id)
        except Exception as e:
            print(f"Görsel yükleme uyarısı (Medyasız devam ediliyor): {e}")

    try:
        tweet = await client.create_tweet(text=text, media_ids=media_ids if media_ids else None)
    except Exception as e:
        print(f"❌ Tweet oluşturma hatası: {e}")
        tweet = None
    
    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
        except Exception:
            pass

    if tweet:
        await asyncio.sleep(random.randint(5, 10))
        comment_prompt = f"Write a short, engaging follow-up English comment or question for this tweet: '{text}'. Under 120 chars."
        comment_text = generate_ai_text(comment_prompt)
        try:
            await client.create_tweet(text=comment_text, reply_to=tweet.id)
        except Exception as e:
            print(f"Yorum atma hatası: {e}")
        return tweet.id

    return None

# --- AKILLI TAKİP VE ETKİLEŞİM MODÜLÜ ---
async def engage_with_target():
    client = Client('en-US')
    cookies = parse_cookies_data(X_COOKIES_JSON)
    if not cookies:
        return

    try:
        client.set_cookies(cookies)
    except Exception as e:
        print(f"❌ Çerezler atanırken hata oluştu: {e}")
        return

    targets = ["NatGeo", "EarthPix", "BBCEarth", "OurPlanet"]
    target = random.choice(targets)
    
    await asyncio.sleep(random.randint(15, 30))
    try:
        user = await client.get_user_by_screen_name(target)
        await user.follow()
        
        tweets = await user.get_tweets('Tweets', count=3)
        if tweets:
            prompt = f"Write a thoughtful, smart English comment on a nature post by @{target}. Under 140 chars. Sound natural."
            reply_text = generate_ai_text(prompt)
            await client.create_tweet(text=reply_text, reply_to=tweets[0].id)
            print(f"🎯 @{target} hesabı takip edildi ve yorum yapıldı.")
    except Exception as e:
        print(f"Etkileşim hatası: {e}")

# --- GÖREV SEÇİCİ ---
def run_job():
    now_hour = datetime.now().hour

    if 7 <= now_hour < 9:
        print("☀️ Hava durumu görevi çalıştırılıyor...")
        text = get_weather_info()
        img = fetch_hd_image("morning sunrise nature")
        asyncio.run(post_to_x(text, img))
        notify_telegram(f"☀️ **Sabah Hava Durumu Paylaşıldı!**\n\n_{text}_")

    elif now_hour in [15, 21]:
        print("🎥 Video görevi çalıştırılıyor...")
        ctx = get_season_context()
        prompt = f"Write a short, engaging English nature fact or reel caption. Context: {ctx}. Max 200 chars."
        text = generate_ai_text(prompt)
        img = fetch_hd_image("nature video style landscape")
        asyncio.run(post_to_x(text, img))
        notify_telegram(f"🎥 **Video İçerik Paylaşıldı!**\n\n_{text}_")

    elif now_hour == 22:
        print("🎯 Etkileşim ve takip görevi çalıştırılıyor...")
        asyncio.run(engage_with_target())
        notify_telegram("🎯 **Hedef sayfalar ile etkileşim sağlandı.**")

    else:
        print("📸 Görsel içerik görevi çalıştırılıyor...")
        ctx = get_season_context()
        prompt = f"Write a beautiful, inspiring English tweet about nature landscapes or wildlife. Context: {ctx}. Max 220 chars. 2 hashtags."
        text = generate_ai_text(prompt)
        img = fetch_hd_image("scenic nature landscape")
        asyncio.run(post_to_x(text, img))
        notify_telegram(f"📸 **Görsel İçerik Paylaşıldı!**\n\n_{text}_")

if __name__ == "__main__":
    print("🚀 GitHub Actions İşlemi Başlatıldı...")
    run_job()
    print("✅ Görev tamamlandı. Çalışma sonlandırılıyor.")
    sys.exit(0)
