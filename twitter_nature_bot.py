import asyncio
import json
import os
import re
import sys
import time
import requests

# ============================================================
# TWIKIT KEY_BYTE PATCH
# ============================================================

try:
    import twikit.x_client_transaction.transaction as tx

    _orig_get_indices = tx.ClientTransaction.get_indices

    async def _patched_get_indices(self, response_text, *args, **kwargs):
        try:
            return await _orig_get_indices(
                self,
                response_text,
                *args,
                **kwargs
            )

        except Exception as original_error:

            # Twikit bazı sürümlerde BeautifulSoup nesnesi
            # gönderebiliyor. Önce güvenli şekilde string'e çeviriyoruz.
            if hasattr(response_text, "get_text"):
                text = response_text.get_text()
            else:
                text = str(response_text)

            # KEY_BYTE değerlerini bulmaya çalış
            row_index_match = re.search(
                r'\((\d+)\)',
                text
            )

            key_bytes_match = re.search(
                r'\[([\d,\s]+)\]',
                text
            )

            if row_index_match and key_bytes_match:

                row_index = int(
                    row_index_match.group(1)
                )

                key_bytes = [
                    int(x.strip())
                    for x in key_bytes_match.group(1).split(",")
                ]

                print(
                    "✅ KEY_BYTE patch başarılı: "
                    f"row_index={row_index}, "
                    f"key_bytes={key_bytes}"
                )

                return row_index, key_bytes

            print(
                "⚠️ KEY_BYTE otomatik patch'i başarısız."
            )

            print(
                f"Twikit hatası: {original_error}"
            )

            print(
                f"Response tipi: {type(response_text).__name__}"
            )

            print(
                f"Response başlangıcı: {text[:500]}"
            )

            # Orijinal hatayı koru
            raise original_error

    tx.ClientTransaction.get_indices = _patched_get_indices

    tx.ON_DEMAND_FILE_REGEX = re.compile(
        r'https://abs\.twimg\.com/responsive-web/client-web/'
        r'ondemand\.s\.[a-z0-9]+a\.js'
    )

    print("✅ Twikit KEY_BYTE patch aktif.")

except Exception as e:
    print(
        f"⚠️ Twikit patch uygulanamadı: {e}"
    )


# ============================================================
# IMPORTS
# ============================================================

from twikit import Client
from google import genai

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


# ============================================================
# AYARLAR
# ============================================================

sys.stdout.reconfigure(line_buffering=True)

X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
X_COOKIES_JSON = os.environ.get("X_COOKIES_JSON")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)

TELEGRAM_CHAT_ID = os.environ.get(
    "TELEGRAM_CHAT_ID"
)

COOKIES_FILE = "cookies.json"

client = Client("en-US")


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_log(message: str):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "ℹ️ Telegram bilgileri bulunamadı."
        )
        return

    try:

        url = (
            "https://api.telegram.org/"
            f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }

        response = requests.post(
            url,
            json=payload,
            timeout=10
        )

        if not response.ok:
            print(
                "⚠️ Telegram gönderim hatası: "
                f"{response.text}"
            )

    except Exception as e:

        print(
            f"⚠️ Telegram log hatası: {e}"
        )


# ============================================================
# COOKIE YÜKLEME
# ============================================================

def load_cookies(raw_cookies):

    if isinstance(raw_cookies, list):

        return {
            cookie["name"]: cookie["value"]
            for cookie in raw_cookies
            if "name" in cookie
            and "value" in cookie
        }

    if isinstance(raw_cookies, dict):
        return raw_cookies

    raise ValueError(
        "Cookie formatı geçersiz."
    )


# ============================================================
# LOGIN
# ============================================================

async def login():

    print(
        "🔑 X oturumu kontrol ediliyor..."
    )

    # --------------------------------------------------------
    # 1. GitHub Secret / Environment Cookie
    # --------------------------------------------------------

    if X_COOKIES_JSON and X_COOKIES_JSON.strip():

        try:

            raw_cookies = json.loads(
                X_COOKIES_JSON.strip()
            )

            cookies_dict = load_cookies(
                raw_cookies
            )

            client.set_cookies(
                cookies_dict
            )

            print(
                "✅ X_COOKIES_JSON üzerinden "
                "oturum yüklendi."
            )

            return

        except Exception as e:

            print(
                "⚠️ X_COOKIES_JSON okunamadı: "
                f"{e}"
            )


    # --------------------------------------------------------
    # 2. Local cookies.json
    # --------------------------------------------------------

    if (
        os.path.exists(COOKIES_FILE)
        and os.path.getsize(COOKIES_FILE) > 0
    ):

        try:

            with open(
                COOKIES_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                raw_cookies = json.load(f)

            cookies_dict = load_cookies(
                raw_cookies
            )

            client.set_cookies(
                cookies_dict
            )

            print(
                "✅ cookies.json üzerinden "
                "oturum yüklendi."
            )

            return

        except Exception as e:

            print(
                "⚠️ cookies.json okunamadı: "
                f"{e}"
            )


    # --------------------------------------------------------
    # 3. Kullanıcı adı / e-posta / şifre
    # --------------------------------------------------------

    if not X_PASSWORD:

        raise Exception(
            "❌ X_PASSWORD bulunamadı. "
            "GitHub Secrets bölümüne X_PASSWORD "
            "veya X_COOKIES_JSON eklemelisin."
        )

    print(
        "⚠️ Cookie bulunamadı."
    )

    print(
        "🔐 Kullanıcı bilgileriyle X giriş "
        "deneniyor..."
    )

    await client.login(
        auth_info_1=X_USERNAME,
        auth_info_2=X_EMAIL,
        password=X_PASSWORD
    )

    print(
        "✅ X giriş başarılı."
    )


# ============================================================
# AI TWEET ÜRETİMİ
# ============================================================

def generate_ai_tweet():

    prompt = """
Sen doğa, okyanus, canlılar dünyası ve çevre
hakkında büyüleyici bilgiler paylaşan uzman
bir içerik üreticisisin.

Takipçilerin ilgisini çekecek, samimi ve merak
uyandırıcı 1 adet Türkçe X gönderisi yaz.

Kurallar:

- İçerik tamamen doğa, deniz canlıları,
  hayvanlar veya ekosistem ile ilgili olsun.
- Maksimum 200 karakter olsun.
- En fazla 3 alakalı hashtag kullan.
- Türkçe yaz.
- Sadece gönderinin kendisini yaz.
- "Üretici:", "Bot:", "Sabit Havuz"
  gibi ifadeler kullanma.
- Kaynak veya dipnot ekleme.
"""

    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------

    if GEMINI_API_KEY:

        for attempt in range(1, 4):

            try:

                print(
                    f"🤖 Gemini deneniyor "
                    f"({attempt}/3)..."
                )

                ai_client = genai.Client(
                    api_key=GEMINI_API_KEY
                )

                response = (
                    ai_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                )

                if response and response.text:

                    tweet = response.text.strip()

                    # AI bazen başına/sonuna tırnak koyabiliyor
                    tweet = tweet.strip(
                        "\"'"
                    )

                    if len(tweet) <= 200:

                        return (
                            tweet,
                            "Gemini 2.5 Flash"
                        )

                    print(
                        "⚠️ Gemini 200 karakterden "
                        "uzun içerik üretti."
                    )

            except Exception as e:

                print(
                    f"⚠️ Gemini deneme "
                    f"{attempt}/3 başarısız: {e}"
                )

                time.sleep(2)


    # --------------------------------------------------------
    # GROQ
    # --------------------------------------------------------

    if GROQ_API_KEY and GROQ_AVAILABLE:

        try:

            print(
                "🤖 Groq deneniyor..."
            )

            groq_client = Groq(
                api_key=GROQ_API_KEY
            )

            completion = (
                groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=150
                )
            )

            content = (
                completion
                .choices[0]
                .message
                .content
            )

            if content:

                tweet = content.strip()

                tweet = tweet.strip(
                    "\"'"
                )

                if len(tweet) <= 200:

                    return (
                        tweet,
                        "Groq (Llama-3.3-70b)"
                    )

                print(
                    "⚠️ Groq 200 karakterden "
                    "uzun içerik üretti."
                )

        except Exception as e:

            print(
                f"⚠️ Groq tweet üretimi "
                f"başarısız: {e}"
            )


    raise Exception(
        "❌ Hiçbir yapay zeka servisi "
        "içerik üretemedi!"
    )


# ============================================================
# TWEET PAYLAŞ
# ============================================================

async def post_daily_tweet():

    # X'e giriş
    await login()

    # AI tweet oluştur
    tweet_text, ai_model = (
        generate_ai_tweet()
    )

    print(
        "\n🚀 Tweet paylaşılıyor..."
    )

    print(
        f"🤖 AI: {ai_model}"
    )

    print(
        f"📝 Tweet:\n{tweet_text}"
    )

    print(
        f"📏 Karakter: {len(tweet_text)}"
    )

    # X'te paylaş
    await client.create_tweet(
        text=tweet_text
    )

    print(
        "✅ Tweet başarıyla paylaşıldı!"
    )

    # Telegram
    telegram_msg = (
        "✅ *Yeni Doğa Tweeti Paylaşıldı!*\n\n"
        f"📝 *İçerik:*\n{tweet_text}\n\n"
        f"🤖 *Kullanılan AI:* `{ai_model}`"
    )

    send_telegram_log(
        telegram_msg
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            post_daily_tweet()
        )

    except Exception as e:

        print(
            "\n❌ PROGRAM HATASI:"
        )

        print(
            str(e)
        )

        send_telegram_log(
            f"❌ *Bot hata verdi:*\n\n"
            f"`{str(e)}`"
        )

        sys.exit(1)
