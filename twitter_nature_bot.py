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
#
# X, Mart 2026'da ondemand.s.js formatını değiştirdi.
# Twikit 2.3.3'ün eski regex'i bu nedenle:
#     Couldn't get KEY_BYTE indices
# hatası verebiliyor.
#
# Bu patch, güncel topluluk düzeltmesini uygular:
# 1) X ana sayfasındaki ondemand.s indeksini bulur
# 2) ilgili hash'i bulur
# 3) gerçek ondemand.s.<hash>a.js dosyasını indirir
# 4) KEY_BYTE indekslerini o JS içinden çıkarır
#
# Patch, "from twikit import Client" IMPORT'undan önce çalışmalıdır.

try:
    import twikit.x_client_transaction.transaction as tx

    tx.ON_DEMAND_FILE_REGEX = re.compile(
        r""",(\d+):["']ondemand\.s["']""",
        flags=(re.VERBOSE | re.MULTILINE)
    )

    tx.ON_DEMAND_HASH_PATTERN = r',{}:"([0-9a-f]+)"'

    async def _patched_get_indices(
        self,
        home_page_response,
        session,
        headers
    ):
        key_byte_indices = []

        response = (
            self.validate_response(home_page_response)
            or self.home_page_response
        )

        response_text = str(response)

        # Yeni X formatı:
        # ,<index>:"ondemand.s"
        on_demand_file = tx.ON_DEMAND_FILE_REGEX.search(response_text)

        if not on_demand_file:
            raise Exception(
                "X ana sayfasında ondemand.s referansı bulunamadı."
            )

        on_demand_file_index = on_demand_file.group(1)

        # Aynı index'e karşılık gelen hash:
        # ,<index>:"<hash>"
        hash_regex = re.compile(
            tx.ON_DEMAND_HASH_PATTERN.format(
                on_demand_file_index
            )
        )

        hash_match = hash_regex.search(response_text)

        if not hash_match:
            raise Exception(
                "ondemand.s hash değeri bulunamadı."
            )

        filename = hash_match.group(1)

        on_demand_file_url = (
            "https://abs.twimg.com/"
            "responsive-web/client-web/"
            f"ondemand.s.{filename}a.js"
        )

        on_demand_file_response = await session.request(
            method="GET",
            url=on_demand_file_url,
            headers=headers
        )

        key_byte_indices_match = tx.INDICES_REGEX.finditer(
            str(on_demand_file_response.text)
        )

        for item in key_byte_indices_match:
            key_byte_indices.append(item.group(2))

        if not key_byte_indices:
            raise Exception(
                "Couldn't get KEY_BYTE indices"
            )

        key_byte_indices = list(
            map(int, key_byte_indices)
        )

        print(
            "✅ KEY_BYTE patch başarılı: "
            f"indices={key_byte_indices}"
        )

        return (
            key_byte_indices[0],
            key_byte_indices[1:]
        )

    tx.ClientTransaction.get_indices = _patched_get_indices

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

    # Sonraki çalıştırmalarda tekrar login olmamak için
    # Twikit session cookie'lerini kaydet.
    try:
        client.save_cookies(COOKIES_FILE)
        print(
            f"🍪 X cookie oturumu kaydedildi: {COOKIES_FILE}"
        )
    except Exception as e:
        print(
            f"⚠️ Cookie kaydedilemedi: {e}"
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
