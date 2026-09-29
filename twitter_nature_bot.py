import asyncio
import json
import os
import random
import sys
import requests
from google import genai
from groq import Groq
from twikit import Client

sys.stdout.reconfigure(line_buffering=True)

# Environment Değişkenleri
X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
X_COOKIES_JSON = os.environ.get("X_COOKIES_JSON")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

COOKIES_FILE = "cookies.json"
client = Client("en-US")


def send_telegram_log(message: str):
    """Sadece sana Telegram'dan gizli bildirim atar."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram log hatası: {e}")


async def login():
    print("🔑 X oturumu kontrol ediliyor...")
    if X_COOKIES_JSON and X_COOKIES_JSON.strip():
        try:
            cookies_dict = json.loads(X_COOKIES_JSON.strip())
            client.set_cookies(cookies_dict)
            print("✅ Environment 'X_COOKIES_JSON' üzerinden oturum yüklendi.")
            return
        except Exception as e:
            print(f"⚠️ Environment cookies okuma hatası: {e}")

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                cookies_dict = json.load(f)
                client.set_cookies(cookies_dict)
                print("✅ Yerel 'cookies.json' dosyasından oturum yüklendi.")
                return
        except Exception as e:
            print(f"⚠️ Dosya cookies okuma hatası: {e}")

    print("⚠️ Çerez bulunamadı, kullanıcı bilgileriyle giriş deneniyor...")
    await client.login(
        auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD
    )


def generate_ai_tweet():
    """Sabit havuz kaldırıldı! Sadece Gemini ve Groq üretir."""
    prompt = (
        "Sen doğa, okyanus, canlılar dünyası ve çevre hakkında büyüleyici bilgiler paylaşan uzman bir içerik üreticisisin. "
        "Takipçilerin ilgisini çekecek, samimi ve merak uyandıran 1 adet Türkçe X (Twitter) gönderisi yaz.\n\n"
        "Kurallar:\n"
        "- İçerik tamamen doğa, deniz canlıları, hayvanlar veya ekosistem ile ilgili olsun.\n"
        "- Maksimum 200 karakter olsun.\n"
        "- En fazla 3 adet alakalı hashtag ekle (#doğa #nature gibi).\n"
        "- Kesinlikle 'Üretici:', 'Bot:', 'Sabit Havuz' veya kaynak/dipnot etiketleri EKLEME."
    )

    # 1. Öncelik: Gemini API
    if GEMINI_API_KEY:
        try:
            ai_client = genai.Client(api_key=GEMINI_API_KEY)
            response = ai_client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            if response.text:
                return response.text.strip(), "Gemini 2.0 Flash"
        except Exception as e:
            print(f"⚠️ Gemini tweet üretimi başarısız, Groq'a geçiliyor: {e}")

    # 2. Öncelik (Yedek): Groq API
    if GROQ_API_KEY:
        try:
            groq_client = Groq(api_key=GROQ_API_KEY)
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150,
            )
            if completion.choices[0].message.content:
                return completion.choices[0].message.content.strip(), (
                    "Groq (Llama-3.3)"
                )
        except Exception as e:
            print(f"⚠️ Groq tweet üretimi başarısız: {e}")

    raise Exception(
        "❌ Hiçbir Yapay Zeka servisi çalışmadı! API anahtarlarını kontrol et."
    )


async def post_daily_tweet():
    await login()

    # 1. Yapay Zekadan Tweet ve Hangi AI Üretti Bilgisi Alınır
    tweet_text, ai_model = generate_ai_tweet()

    # 2. X'e SADECE TEMİZ TWEET ATILIR (X'te "Üretici:" vs. gözükmez!)
    print(f"🚀 Tweet Paylaşılıyor ({ai_model}):\n{tweet_text}")
    await client.create_tweet(text=tweet_text)

    # 3. Sana Özel Telegram Bildirimi (AI Modeli Burada Yazar)
    telegram_msg = (
        f"✅ **Yeni Doğa Tweeti Paylaşıldı!**\n\n"
        f"📝 **İçerik:**\n{tweet_text}\n\n"
        f"🤖 **Kullanılan AI:** `{ai_model}`"
    )
    send_telegram_log(telegram_msg)


if __name__ == "__main__":
    asyncio.run(post_daily_tweet())
