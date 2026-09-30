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

sys.stdout.reconfigure(line_buffering=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_log(message: str):
"""Telegram'a mesaj gönderir."""

```
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("⚠️ Telegram bilgileri bulunamadı.")
    return

url = (
    f"https://api.telegram.org/bot"
    f"{TELEGRAM_BOT_TOKEN}/sendMessage"
)

payload = {
    "chat_id": TELEGRAM_CHAT_ID,
    "text": message
}

try:
    response = requests.post(
        url,
        json=payload,
        timeout=20
    )

    if response.ok:
        print("✅ Telegram bildirimi gönderildi.")
    else:
        print(
            f"⚠️ Telegram hatası: "
            f"{response.status_code} {response.text}"
        )

except Exception as e:
    print(f"⚠️ Telegram bağlantı hatası: {e}")
```

def generate_ai_tweet():
"""Gemini ile doğa içerikli kısa paylaşım üretir."""

```
prompt = """
```

Sen Türkçe içerik üreten bir doğa ve bilim içerik editörüsün.

Twitter/X için kısa, ilgi çekici ve bilgi verici bir doğa paylaşımı hazırla.

Kurallar:

* Türkçe yaz.
* Maksimum 200 karakter olsun.
* Doğa, hayvanlar, bitkiler, okyanuslar, uzay veya çevre konularından birini seç.
* İlginç ve mümkün olduğunca doğrulanabilir bir bilgi kullan.
* Abartılı veya uydurma bilgi verme.
* En fazla 3 hashtag kullan.
* Emoji kullanabilirsin.
* Giriş cümlesi dikkat çekici olsun.
* Sadece paylaşım metnini döndür.
* Açıklama yapma.
* Tırnak işareti kullanma.
  """

  # ---------------------------------------------------------

  # 1. GEMINI

  # ---------------------------------------------------------

  if GEMINI_API_KEY:
  try:
  print("🤖 Gemini ile içerik üretiliyor...")

  ```
        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        text = (response.text or "").strip()

        if text:
            text = text.replace("\n", " ").strip()

            if len(text) > 200:
                text = text[:197] + "..."

            print("✅ Gemini içerik üretti.")

            return text, "Gemini"

    except Exception as e:
        print(f"⚠️ Gemini başarısız: {e}")
        print("🔄 Groq yedek modele geçiliyor...")
  ```

  # ---------------------------------------------------------

  # 2. GROQ YEDEK

  # ---------------------------------------------------------

  if GROQ_API_KEY and GROQ_AVAILABLE:
  try:
  print("🤖 Groq ile içerik üretiliyor...")

  ```
        groq_client = Groq(
            api_key=GROQ_API_KEY
        )

        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.8,
            max_tokens=150
        )

        text = (
            response.choices[0]
            .message
            .content
            .strip()
        )

        if text:
            text = text.replace("\n", " ").strip()

            if len(text) > 200:
                text = text[:197] + "..."

            print("✅ Groq içerik üretti.")

            return text, "Groq"

    except Exception as e:
        print(f"❌ Groq başarısız: {e}")
  ```

  raise Exception(
  "Gemini veya Groq ile içerik üretilemedi."
  )

def prepare_daily_tweet():
"""Günün paylaşımını hazırlar."""

```
print("=" * 60)
print("🌿 DOĞA İÇERİK BOTU")
print("=" * 60)

tweet_text, ai_model = generate_ai_tweet()

print()
print("📝 OLUŞTURULAN PAYLAŞIM:")
print("-" * 60)
print(tweet_text)
print("-" * 60)
print(f"🤖 Model: {ai_model}")
print(f"📏 Karakter sayısı: {len(tweet_text)}")

return tweet_text, ai_model
```

def main():
"""Ana program."""

```
try:
    print("🚀 Bot başlatılıyor...")
    print()

    tweet_text, ai_model = prepare_daily_tweet()

    print()
    print("⚠️ Twikit tamamen kaldırıldı.")
    print("ℹ️ X otomatik paylaşımı şu anda yapılmıyor.")
    print("✅ İçerik başarıyla oluşturuldu.")

    telegram_message = (
        "🌿 Günlük Doğa İçeriği\n\n"
        f"{tweet_text}\n\n"
        f"🤖 AI: {ai_model}\n"
        f"📏 {len(tweet_text)} karakter\n\n"
        "⚠️ Twikit kaldırıldı.\n"
        "ℹ️ X paylaşımı yapılmadı."
    )

    send_telegram_log(telegram_message)

    print()
    print("🎉 PROGRAM BAŞARIYLA TAMAMLANDI.")

    return 0

except Exception as e:

    print()
    print("=" * 60)
    print("❌ PROGRAM HATASI")
    print("=" * 60)
    print(str(e))
    print("=" * 60)

    send_telegram_log(
        f"❌ Doğa botu hata verdi:\n\n{str(e)}"
    )

    return 1
```

if **name** == "**main**":
sys.exit(main())
