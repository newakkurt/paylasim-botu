import os
import sys
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
            timeout=20
        )
        print("Telegram bildirimi gönderildi.")
    except Exception as e:
        print("Telegram hatası:", e)


def gemini_text():
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY yok.")

    prompt = """
Türkçe kısa bir doğa bilgisi üret.
X paylaşımı için yaz.
Maksimum 200 karakter.
Gerçek ve doğrulanabilir bilgi kullan.
En fazla 3 hashtag.
Sadece paylaşım metnini yaz.
"""

    client = genai.Client(api_key=GEMINI_API_KEY)

    result = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt
    )

    text = (result.text or "").strip()

    if not text:
        raise Exception("Gemini boş cevap verdi.")

    return text


def groq_text():
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY yok.")

    prompt = """
Türkçe kısa bir doğa bilgisi üret.
X paylaşımı için yaz.
Maksimum 200 karakter.
Gerçek ve doğrulanabilir bilgi kullan.
En fazla 3 hashtag.
Sadece paylaşım metnini yaz.
"""

    client = Groq(api_key=GROQ_API_KEY)

    result = client.chat.completions.create(
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

    text = result.choices[0].message.content.strip()

    if not text:
        raise Exception("Groq boş cevap verdi.")

    return text


def create_post():
    try:
        print("Gemini deneniyor...")
        return gemini_text(), "Gemini"

    except Exception as e:
        print("Gemini başarısız:", e)
        print("Groq yedek olarak deneniyor...")

        return groq_text(), "Groq"


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
        json={"text": text},
        timeout=30
    )

    print("X API:", response.status_code)

    if not response.ok:
        print(response.text)
        raise Exception("X paylaşımı başarısız.")

    data = response.json()

    post_id = data["data"]["id"]

    return post_id


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
        print("PAYLASIM:")
        print("-" * 60)
        print(text)
        print("-" * 60)
        print("Model:", model)
        print("Karakter:", len(text))

        post_id = post_x(text)

        post_url = "https://x.com/i/web/status/" + post_id

        print()
        print("X PAYLASIMI BASARILI")
        print(post_url)

        send_telegram(
            "🌿 Günlük Doğa İçeriği\n\n"
            + text
            + "\n\n"
            + "🤖 Model: "
            + model
            + "\n"
            + "✅ X paylaşımı başarılı\n"
            + post_url
        )

        return 0

    except Exception as e:
        print()
        print("PROGRAM HATASI")
        print(str(e))

        send_telegram(
            "❌ Doğa botu hata verdi:\n\n"
            + str(e)
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
