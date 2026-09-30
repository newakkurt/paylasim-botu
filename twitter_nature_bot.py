import os
import sys
import requests

from google import genai
from groq import Groq

sys.stdout.reconfigure(line_buffering=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN")

def send_telegram_log(message):
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
print("Telegram bilgileri bulunamadı.")
return

```
url = (
    "https://api.telegram.org/bot"
    + TELEGRAM_BOT_TOKEN
    + "/sendMessage"
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
        print("Telegram bildirimi gönderildi.")
    else:
        print(
            "Telegram hatası:",
            response.status_code,
            response.text
        )

except Exception as e:
    print("Telegram bağlantı hatası:", e)
```

def generate_with_gemini():
if not GEMINI_API_KEY:
raise Exception("GEMINI_API_KEY bulunamadı.")

```
print("Gemini ile içerik üretiliyor...")

prompt = """
```

Sen Türkçe doğa ve bilim içerikleri üreten bir editörsün.

X için kısa, ilgi çekici ve bilgi verici bir paylaşım oluştur.

Kurallar:

* Türkçe yaz.
* Maksimum 200 karakter.
* Hayvanlar, bitkiler, okyanuslar, ormanlar veya çevre konularından birini seç.
* Doğrulanabilir bir bilgi kullan.
* Uydurma bilgi verme.
* En fazla 3 hashtag kullan.
* Emoji kullanabilirsin.
* Sadece paylaşım metnini döndür.
* Açıklama yapma.
* Tırnak işareti kullanma.
  """

  client = genai.Client(
  api_key=GEMINI_API_KEY
  )

  response = client.models.generate_content(
  model="gemini-3.8-flash",
  contents=prompt
  )

  text = (response.text or "").strip()

  if not text:
  raise Exception("Gemini boş cevap döndürdü.")

  return text

def generate_with_groq():
if not GROQ_API_KEY:
raise Exception("GROQ_API_KEY bulunamadı.")

```
print("Groq yedek model devreye giriyor...")

prompt = """
```

Türkçe, kısa ve ilginç bir doğa bilgisi yaz.

Kurallar:

* X paylaşımı için hazırla.
* Maksimum 200 karakter.
* Hayvan, bitki, okyanus, orman veya çevre konusu seç.
* Gerçek ve doğrulanabilir bilgi kullan.
* Uydurma bilgi verme.
* En fazla 3 hashtag kullan.
* Emoji kullanabilirsin.
* Sadece paylaşım metnini yaz.
  """

  client = Groq(
  api_key=GROQ_API_KEY
  )

  response = client.chat.completions.create(
  model="llama-3.1-8b-instant",
  messages=[
  {
  "role": "user",
  "content": prompt
  }
  ],
  temperature=0.7,
  max_tokens=150
  )

  text = (
  response.choices[0]
  .message
  .content
  .strip()
  )

  if not text:
  raise Exception("Groq boş cevap döndürdü.")

  return text

def generate_ai_tweet():
try:
text = generate_with_gemini()
return text, "Gemini"

```
except Exception as gemini_error:

    print()
    print("Gemini başarısız oldu.")
    print("Gemini hatası:", gemini_error)
    print()

    try:
        text = generate_with_groq()
        return text, "Groq"

    except Exception as groq_error:

        print("Groq da başarısız oldu.")
        print("Groq hatası:", groq_error)

        raise Exception(
            "Gemini ve Groq içerik üretemedi."
        )
```

def clean_tweet(text):
text = text.replace("\n", " ")
text = text.strip()

```
if len(text) > 200:
    text = text[:197] + "..."

return text
```

def post_to_x(text):
if not X_ACCESS_TOKEN:
raise Exception(
"X_ACCESS_TOKEN GitHub Secrets içinde bulunamadı."
)

```
print("X API'ye bağlanılıyor...")

url = "https://api.x.com/2/tweets"

headers = {
    "Authorization": "Bearer " + X_ACCESS_TOKEN,
    "Content-Type": "application/json"
}

payload = {
    "text": text
}

response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=30
)

print("X API HTTP:", response.status_code)

if not response.ok:
    print("X API cevabı:")
    print(response.text)

    raise Exception(
        "X paylaşımı başarısız oldu."
    )

data = response.json()

if "data" not in data:
    raise Exception(
        "X API Post ID döndürmedi."
    )

post_id = data["data"]["id"]

print("X paylaşımı başarılı.")
print("Post ID:", post_id)

return post_id
```

def main():
print("=" * 60)
print("DOGA ICERIK BOTU")
print("=" * 60)

```
try:

    tweet_text, ai_model = generate_ai_tweet()

    tweet_text = clean_tweet(tweet_text)

    print()
    print("OLUSTURULAN PAYLASIM:")
    print("-" * 60)
    print(tweet_text)
    print("-" * 60)
    print("AI:", ai_model)
    print("Karakter sayisi:", len(tweet_text))

    print()

    post_id = post_to_x(tweet_text)

    post_url = (
        "https://x.com/i/web/status/"
        + str(post_id)
    )

    telegram_message = (
        "🌿 Günlük Doğa İçeriği\n\n"
        + tweet_text
        + "\n\n"
        + "🤖 AI: "
        + ai_model
        + "\n"
        + "📏 Karakter: "
        + str(len(tweet_text))
        + "\n\n"
        + "✅ X paylaşımı başarılı\n"
        + post_url
    )

    send_telegram_log(
        telegram_message
    )

    print()
    print("PROGRAM BASARIYLA TAMAMLANDI.")
    print("X:", post_url)

    return 0

except Exception as e:

    print()
    print("=" * 60)
    print("PROGRAM HATASI")
    print("=" * 60)
    print(str(e))
    print("=" * 60)

    send_telegram_log(
        "❌ Doğa botu hata verdi:\n\n"
        + str(e)
    )

    return 1
```

if **name** == "**main**":
sys.exit(main())
