import asyncio
import json
import os
import re
import sys
import time
import requests

# --- TWIKIT KEY_BYTE DÜZELTME YAMASI (MONKEY PATCH) ---
try:
    import twikit.x_client_transaction.transaction as tx

    _orig_get_indices = tx.ClientTransaction.get_indices

    async def _patched_get_indices(self, response_text, *args, **kwargs):
        try:
            return await _orig_get_indices(self, response_text, *args, **kwargs)
        except Exception:
            row_index_match = re.search(r'\((\d+)\)', response_text)
            key_bytes_match = re.search(r'\[([\d,\s]+)\]', response_text)
            if row_index_match and key_bytes_match:
                row_index = int(row_index_match.group(1))
                key_bytes = [int(x.strip()) for x in key_bytes_match.group(1).split(',')]
                return row_index, key_bytes
            raise Exception("Couldn't get KEY_BYTE indices via patch")

    tx.ClientTransaction.get_indices = _patched_get_indices

    tx.ON_DEMAND_FILE_REGEX = re.compile(
        r'https://abs\.twimg\.com/responsive-web/client-web/ondemand\.s\.[a-z0-9]+a\.js'
    )
except Exception as e:
    print(f"⚠️ Twikit patch uygulanamadı: {e}")
# ------------------------------------------------------

from twikit import Client
from google import genai
from groq import Groq

# ORTAM DEĞİŞKENLERİ
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


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram bilgileri eksik, bildirim atlanıyor.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN.strip()}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID.strip(),
                "text": message
            },
            timeout=30
        )
        if response.ok:
            print("✅ Telegram bildirimi gönderildi.")
        else:
            print("⚠️ Telegram HTTP hatası:", response.status_code)
    except Exception as e:
        print("⚠️ Telegram hatası:", e)


async def login_x():
    print("🔑 X oturumu açılıyor...")
    
    # 1. Environment'tan COOKIE okuma
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
            print("✅ X_COOKIES_JSON ortam değişkeninden oturum yüklendi.")
            return
        except Exception as e:
            print(f"⚠️ Ortam değişkeni çerez okuma hatası: {e}")

    # 2. Dosyadan COOKIE okuma
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
            print("✅ 'cookies.json' dosyasından oturum yüklendi.")
            return
        except Exception as e:
            print(f"⚠️ Çerez dosyası okuma hatası: {e}")

    # 3. Kullanıcı adı ve şifre ile doğrudan giriş
    if X_USERNAME and X_PASSWORD:
        print("⚠️️ Çerez bulunamadı, kullanıcı adı/şifre ile giriş yapılıyor...")
        await client.login(
            auth_info_1=X_USERNAME,
            auth_info_2=X_EMAIL,
            password=X_PASSWORD
        )
        print("✅ X girişi başarılı.")
        return

    raise Exception("X girişi için ne COOKIE ne de X_USERNAME/X_PASSWORD bulundu!")


def gemini_text():
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY yok.")

    ai_client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = """
Türkçe, kısa ve ilgi çekici bir doğa bilgisi hazırla.

Kurallar:
* 1 veya 2 cümle olsun.
* Maksimum 200 karakter olsun.
* Gerçek ve doğrulanabilir bir bilgi olsun.
* Sonuna 2 veya 3 uygun hashtag ekle.
* Emoji kullanabilirsin.
* Sadece paylaşım metnini döndür.
"""

    last_error = None
    for attempt in range(1, 3):
        try:
            print(f"Gemini API çağrısı yapılıyor (Deneme {attempt})...")
            result = ai_client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )
            text = getattr(result, "text", None)
            if text and text.strip():
                return text.strip()
            raise Exception("Gemini boş cevap döndü.")
        except Exception as e:
            last_error = e
            print(f"Gemini denemesi başarısız: {e}")
            if attempt == 1:
                time.sleep(5)

    raise Exception(f"Gemini başarısız oldu: {last_error}")


def groq_text():
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY yok.")

    groq_client = Groq(api_key=GROQ_API_KEY)
    prompt = """
Türkçe, kısa ve ilgi çekici bir doğa bilgisi hazırla.

Kurallar:
* 1 veya 2 cümle olsun.
* Maksimum 200 karakter olsun.
* Gerçek ve doğrulanabilir bir bilgi olsun.
* Sonuna 2 veya 3 uygun hashtag ekle.
* Emoji kullanabilirsin.
* Sadece paylaşım metnini döndür.
"""

    print("Groq API çağrısı yapılıyor...")
    result = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=300
    )

    if result and result.choices and result.choices[0].message:
        text = result.choices[0].message.content
        if text and text.strip():
            return text.strip()

    raise Exception("Groq boş cevap verdi.")


def create_post():
    print("Gemini deneniyor...")
    try:
        text = gemini_text()
        print("✅ Gemini başarılı.")
        return text, "Gemini"
    except Exception as e:
        print("⚠️️ Gemini başarısız:", e)

    print("Groq yedek olarak deneniyor...")
    try:
        text = groq_text()
        print("✅ Groq başarılı.")
        return text, "Groq"
    except Exception as e:
        print("⚠️ Groq başarısız:", e)
        raise Exception("Hem Gemini hem Groq başarısız oldu.")


async def main():
    print("=" * 60)
    print("DOGA ICERIK BOTU")
    print("=" * 60)

    try:
        # 1. İçerik üret
        text, model = create_post()
        text = text.replace("\n", " ").strip()

        if len(text) > 200:
            text = text[:197] + "..."

        print(f"\nKULLANILAN MODEL: {model}")
        print(f"OLUSTURULAN PAYLASIM:\n{text}")
        print(f"Karakter sayısı: {len(text)}\n")

        # 2. X Login & Tweet Gönderme
        await login_x()
        print("🚀 X'e gönderiliyor...")
        tweet = await client.create_tweet(text=text)
        
        tweet_id = getattr(tweet, "id", None)
        post_url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "X Linki Alınamadı"

        print("✅ X paylaşımı başarılı.")
        print("Post ID:", tweet_id)

        # 3. Telegram Bildirimi
        telegram_message = (
            "✅ **DOGA ICERIK BOTU BASARILI**\n\n"
            f"**Model:** {model}\n"
            f"**Paylaşım:**\n{text}\n\n"
            f"**Link:** {post_url}"
        )
        send_telegram(telegram_message)

        print("\n" + "=" * 60)
        print("PROGRAM BASARIYLA TAMAMLANDI.")
        print("=" * 60)
        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print("PROGRAM HATASI")
        print("=" * 60)
        print(e)

        send_telegram(f"❌ **DOGA ICERIK BOTU HATA VERDI**\n\n{e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
