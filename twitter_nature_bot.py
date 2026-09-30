import asyncio
import json
import os
import sys
import time
import requests
from google import genai

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from twikit import Client

sys.stdout.reconfigure(line_buffering=True)

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
            raw_cookies = json.loads(X_COOKIES_JSON.strip())
            if isinstance(raw_cookies, list):
                cookies_dict = {
                    cookie["name"]: cookie["value"]
                    for cookie in raw_cookies
                    if "name" in cookie and "value" in cookie
                }
            else:
                cookies_dict = raw_cookies

            client.set_cookies(cookies_dict)
            print("✅ Environment 'X_COOKIES_JSON' üzerinden oturum yüklendi.")
            return
        except Exception as e:
            print(f"⚠️ Environment cookies okuma hatası: {e}")

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                raw_cookies = json.load(f)
                if isinstance(raw_cookies, list):
                    cookies_dict = {
                        cookie["name"]: cookie["value"]
                        for cookie in raw_cookies
                        if "name" in cookie and "value" in cookie
                    }
                else:
                    cookies_dict = raw_cookies

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
    prompt = (
        "Sen doğa, okyanus, canlılar dünyası ve çevre hakkında büyüleyici"
        " bilgiler paylaşan uzman bir içerik üreticisisin. Takipçilerin ilgisini"
        " çekecek, samimi ve merak uyandıran 1 adet Türkçe X (Twitter) gönderisi"
        " yaz.\n\nKurallar:\n- İçerik tamamen doğa, deniz canlıları, hayvanlar"
        " veya ekosistem ile ilgili olsun.\n- Maksimum 200 karakter olsun.\n-"
        " En fazla 3 adet alakalı hashtag ekle (#doğa #nature gibi).\n- Kesinlikle"
        " 'Üretici:', 'Bot:', 'Sabit Havuz' veya kaynak/dipnot etiketleri"
        " EKLEME."
    )

    # 1. Gemini (Doğru model isimleri ile Retry mekanizması)
    if GEMINI_API_KEY:
        # Geçerli Gemini modelleri
        gemini_models = ["gemini-2.5-flash", "gemini-1.5-flash"]
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        
        for model_name in gemini_models:
            for attempt in range(1, 3):
                try:
                    print(f"🤖 Gemini deneniyor: {model_name} (Deneme {attempt})...")
                    response = ai_client.models.generate_content(
                        model=model_name, contents=prompt
                    )
                    if response.text:
                        return response.text.strip(), f"Gemini ({model_name})"
                except Exception as e:
                    print(f"⚠️ Gemini ({model_name}) hata: {e}")
                    time.sleep(2)

    # 2. Groq Fallback
    if GROQ_API_KEY and GROQ_AVAILABLE:
        groq_models = ["llama-3.3-70b-versatile", "llama3-8b-8192"]
        groq_client = Groq(api_key=GROQ_API_KEY)
        
        for g_model in groq_models:
            try:
                print(f"🤖 Groq deneniyor: {g_model}...")
                completion = groq_client.chat.completions.create(
                    model=g_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=150,
                )
                if completion.choices[0].message.content:
                    return completion.choices[0].message.content.strip(), f"Groq ({g_model})"
            except Exception as e:
                print(f"⚠️ Groq ({g_model}) tweet üretimi başarısız: {e}")

    raise Exception("❌ Hiçbir Yapay Zeka servisi içerik üretemedi!")


async def post_daily_tweet():
    try:
        await login()
        tweet_text, ai_model = generate_ai_tweet()

        print(f"🚀 Tweet Paylaşılıyor ({ai_model}):\n{tweet_text}")
        await client.create_tweet(text=tweet_text)

        telegram_msg = (
            f"✅ **Yeni Doğa Tweeti Paylaşıldı!**\n\n"
            f"📝 **İçerik:**\n{tweet_text}\n\n"
            f"🤖 **Kullanılan AI:** `{ai_model}`"
        )
        send_telegram_log(telegram_msg)
        print("✅ Tweet başarıyla gönderildi ve Telegram'a bildirildi.")
    except Exception as e:
        error_msg = f"❌ **X Otomasyon Hatası:**\n`{str(e)}`"
        print(error_msg)
        send_telegram_log(error_msg)


if __name__ == "__main__":
    asyncio.run(post_daily_tweet())
