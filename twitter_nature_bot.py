import os
import sys
import time
import requests
from google import genai
from groq import Groq

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN")


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram bilgileri yok.")
        return

    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"

    try:
        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            },
            timeout=30
        )
        print("Telegram bildirimi gönderildi.")
    except Exception as e:
        print("Telegram hatası:", e)


def gemini_text():
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY yok.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = """
Türkçe, kısa ve ilgi çekici bir doğa bilgisi hazırla.

Kurallar:
- 1 veya 2 cümle olsun.
- Maksimum 200 karakter olsun.
- Gerçek ve doğrulanabilir bir bilgi olsun.
- Sonuna 2 veya 3 uygun hashtag ekle.
- Emoji kullanabilirsin.
- Sadece paylaşım metnini döndür.

    last_error = None

    for attempt in range(2):
        try:
            result = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )

            text = getattr(result, "text", None)

            if text:
                text = text.strip()

            if text:
                return text

            raise Exception("Gemini boş cevap verdi.")

        except Exception as e:
            last_error = e
            print("Gemini denemesi başarısız:", e)

            if attempt == 0:
                print("Gemini tekrar deneniyor...")
                time.sleep(5)

    raise Exception("Gemini başarısız: " + str(last_error))


def groq_text():
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY yok.")

    client = Groq(api_key=GROQ_API_KEY)

    prompt = """
Türkçe, kısa ve ilgi çekici bir doğa bilgisi hazırla.

Kurallar:
- 1 veya 2 cümle olsun.
- Maksimum 200 karakter olsun.
- Gerçek ve doğrulanabilir bir bilgi olsun.
- Sonuna 2 veya 3 uygun hashtag ekle.
- Emoji kullanabilirsin.
- Sadece paylaşım metnini döndür.

    result = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.8,
        max_tokens=300
    )

    if not result:
        raise Exception("Groq cevap nesnesi boş.")

    if not result.choices:
        raise Exception("Groq choices boş.")

    message = result.choices[0].message

    if not message:
        raise Exception("Groq message boş.")

    text = message.content

    if not text:
        raise Exception("Groq boş cevap verdi.")

    text = text.strip()

    if not text:
        raise Exception("Groq boş cevap verdi.")

    return text


def create_post():
    print("Gemini deneniyor...")

    try:
        text = gemini_text()
        print("Gemini başarılı.")
        return text, "Gemini"

    except Exception as e:
        print("Gemini başarısız:", e)

    print("Groq yedek olarak deneniyor...")

    try:
        text = groq_text()
        print("Groq başarılı.")
        return text, "Groq"

    except Exception as e:
        print("Groq başarısız:", e)
        raise Exception("Hem Gemini hem Groq başarısız oldu.")


def post_x(text):
    if not X_ACCESS_TOKEN:
        raise Exception("X_ACCESS_TOKEN yok.")

    url = "https://api.x.com/2/tweets"

    headers = {
        "Authorization": "Bearer " + X_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json={
            "text": text
        },
        timeout=30
    )

    print("X API HTTP:", response.status_code)

    if not response.ok:
        print("X API cevabı:", response.text)
        raise Exception(
            "X paylaşımı başarısız. HTTP " + str(response.status_code)
        )

    data = response.json()

    if "data" not in data or "id" not in data["data"]:
        print("X API beklenmeyen cevap:", data)
        raise Exception("X gönderi ID'si alınamadı.")

    return data["data"]["id"]


def main():
    print("=" * 60)
    print("DOGA ICERIK BOTU")
    print("=" * 60)

    try:
        text, model = create_post()

        text = text.replace("\n", " ").strip()

        if len(text) > 200:
            text = text[:197] + "..."

        print()
        print("KULLANILAN MODEL:", model)
        print()
        print("OLUSTURULAN PAYLASIM:")
        print(text)
        print()
        print("Karakter sayisi:", len(text))

        print()
        print("X'e gönderiliyor...")

        post_id = post_x(text)

        post_url = "https://x.com/i/web/status/" + post_id

        print("X paylaşımı başarılı.")
        print("Post ID:", post_id)
        print("Post URL:", post_url)

        telegram_message = (
            "DOGA ICERIK BOTU BASARILI\n\n"
            "Model: " + model + "\n"
            "Paylasim:\n" + text + "\n\n"
            "X:\n" + post_url
        )

        send_telegram(telegram_message)

        print()
        print("PROGRAM BASARIYLA TAMAMLANDI.")
        return 0

    except Exception as e:
        print()
        print("PROGRAM HATASI")
        print(e)

        send_telegram(
            "DOGA ICERIK BOTU HATA VERDI\n\n"
            + str(e)
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
```
