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
from google.genai import types
from groq import Groq

# ORTAM DEĞİŞKENLERİ
X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
X_COOKIES_JSON = os.environ.get("X_COOKIES_JSON")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

COOKIES_FILE = "cookies.json"
client = Client("en-US")

PROMPT = """
Türkçe, kısa ve ilgi çekici bir doğa bilgisi hazırla.

Kurallar:
* 1 veya 2 cümle olsun.
* Maksimum 200 karakter olsun.
* Gerçek ve doğrulanabilir bir bilgi olsun.
* Sonuna 2 veya 3 uygun hashtag ekle.
* Emoji kullanabilirsin.
* Sadece paylaşım metnini döndür.
"""

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
            content = X_COOKIES_JSON.strip()
            cookies_dict = {}

            if content.startswith("[") or content.startswith("{"):
                raw_cookies = json.loads(content)
                if isinstance(raw_cookies, list):
                    cookies_dict = {
                        c["name"]: c["value"]
                        for c in raw_cookies if "name" in c and "value" in c
                    }
                else:
                    cookies_dict = raw_cookies
            else:
                for line in content.splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        cookies_dict[parts[5].strip()] = parts[6].strip()

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

    # 3. Kullanıcı adı ve şifre ile giriş
    if X_USERNAME and X_PASSWORD:
        print("⚠️ Çerez bulunamadı, kullanıcı adı/şifre ile giriş yapılıyor...")
        await client.login(
            auth_info_1=X_USERNAME.strip(),
            auth_info_2=X_EMAIL.strip() if X_EMAIL else None,
            password=X_PASSWORD.strip()
        )
        print("✅ X girişi başarılı.")
        return

    raise Exception("X girişi için ne COOKIE ne de X_USERNAME/X_PASSWORD bulundu!")


# --- GEMINI (DOKUNULMADI) ---
def gemini_text():
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY yok.")

    ai_client = genai.Client(api_key=GEMINI_API_KEY)
    last_error = None
    models_to_try = ["gemini-3.8-flash"]

    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    for model_name in models_to_try:
        for attempt in range(1, 3):
            try:
                print(f"Gemini API çağrısı yapılıyor (Model: {model_name}, Deneme: {attempt})...")
                result = ai_client.models.generate_content(
                    model=model_name,
                    contents=PROMPT,
                    config=config
                )
                text = getattr(result, "text", None)
                if text and text.strip():
                    return str(text).strip()
                raise Exception("Gemini boş cevap döndü.")
            except Exception as e:
                last_error = e
                print(f"Gemini denemesi başarısız ({model_name}): {e}")
                time.sleep(2)

    raise Exception(f"Gemini tüm denemelerde başarısız oldu: {last_error}")


# --- GROQ (DOKUNULMADI) ---
def groq_text():
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY yok.")

    groq_client = Groq(api_key=GROQ_API_KEY)
    
    groq_models = [
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "gemma2-9b-it",
        "mixtral-8x7b-32768"
    ]

    for model_name in groq_models:
        try:
            print(f"Groq API çağrısı yapılıyor (Model: {model_name})...")
            result = groq_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": PROMPT}],
                temperature=0.7,
                max_tokens=300
            )

            if result and result.choices and result.choices[0].message:
                text = result.choices[0].message.content
                if text and text.strip():
                    clean_text = str(text).strip()
                    if not clean_text.replace('.', '', 1).isdigit():
                        return clean_text
        except Exception as e:
            print(f"Groq model denemesi başarısız ({model_name}): {e}")

    raise Exception("Groq tüm modellerde başarısız oldu.")


# --- OPENROUTER (DÜZELTİLDİ) ---
def openrouter_text():
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY tanımlı değil.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
        "Content-Type": "application/json"
    }

    free_models = [
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]

    for model in free_models:
        try:
            print(f"OpenRouter API çağrısı yapılıyor (Model: {model})...")
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": PROMPT}],
                    "max_tokens": 300
                },
                timeout=30
            )
            if response.ok:
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                if text and text.strip():
                    return str(text).strip()
            else:
                print(f"OpenRouter HTTP Hatası ({model}): {response.status_code} - {response.text}")
        except Exception as e:
            print(f"OpenRouter denemesi başarısız ({model}): {e}")

    raise Exception("OpenRouter tüm modellerde başarısız oldu.")


def create_post():
    print("1. Gemini deneniyor...")
    try:
        text = gemini_text()
        print("✅ Gemini başarılı.")
        return text, "Gemini"
    except Exception as e:
        print("⚠️ Gemini başarısız:", e)

    print("2. Groq yedek olarak deneniyor...")
    try:
        text = groq_text()
        print("✅ Groq başarılı.")
        return text, "Groq"
    except Exception as e:
        print("⚠️ Groq başarılı.")
        return text, "Groq"

    print("3. OpenRouter yedek olarak deneniyor...")
    try:
        text = openrouter_text()
        print("✅ OpenRouter başarılı.")
        return text, "OpenRouter"
    except Exception as e:
        print("⚠️ OpenRouter başarısız:", e)

    raise Exception("Tüm yapay zeka servisleri (Gemini, Groq, OpenRouter) başarısız oldu.")


async def main():
    print("=" * 60)
    print("DOGA ICERIK BOTU")
    print("=" * 60)

    try:
        # 1. İçerik üret
        text, model = create_post()
        
        # Metnin kesinlikle düzgün bir 'str' olmasını ve tek satırda kalmasını sağlıyoruz
        text = str(text).replace("\n", " ").strip()

        if len(text) > 200:
            text = text[:197] + "..."

        print(f"\nKULLANILAN MODEL: {model}")
        print(f"OLUSTURULAN PAYLASIM:\n{text}")
        print(f"Karakter sayısı: {len(text)}\n")

        # 2. X Login & Tweet Gönderme (Twikit BeautifulSoup hatasına karşı koruma eklendi)
        await login_x()
        print("🚀 X'e gönderiliyor...")
        
        tweet = await client.create_tweet(text=str(text))

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
