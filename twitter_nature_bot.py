import os
import sys
import requests
from google import genai

sys.stdout.reconfigure(line_buffering=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_log(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram bilgileri bulunamadı.")
        return

    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=20)

        if response.ok:
            print("Telegram bildirimi gönderildi.")
        else:
            print("Telegram hatası:", response.status_code)

    except Exception as e:
        print("Telegram bağlantı hatası:", e)


def generate_ai_tweet():
    prompt = """
Sen Türkçe doğa ve bilim içerikleri üreten bir editörsün.

X/Twitter için kısa ve ilgi çekici bir doğa bilgisi hazırla.

Kurallar:
- Türkçe yaz.
- Maksimum 200 karakter.
- Hayvanlar, bitkiler, okyanuslar, ormanlar veya çevre konularından birini seç.
- İlginç ve doğrulanabilir bir bilgi kullan.
- Uydurma bilgi verme.
- En fazla 3 hashtag kullan.
- Emoji kullanabilirsin.
- Sadece paylaşım metnini döndür.
- Açıklama yapma.
"""

    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY bulunamadı.")

    print("Gemini ile içerik üretiliyor...")

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    text = (response.text or "").strip()

    if not text:
        raise Exception("Gemini boş cevap döndürdü.")

    text = text.replace("\n", " ").strip()

    if len(text) > 200:
        text = text[:197] + "..."

    return text


def main():
    print("=" * 60)
    print("DOGA ICERIK BOTU")
    print("=" * 60)

    try:
        tweet_text = generate_ai_tweet()

        print()
        print("OLUSTURULAN PAYLASIM:")
        print("-" * 60)
        print(tweet_text)
        print("-" * 60)
        print("Karakter sayisi:", len(tweet_text))

        print()
        print("Twikit kullanilmiyor.")
        print("X otomatik paylasimi su anda yapilmiyor.")

        telegram_message = (
            "Gunluk Doga Icerigi\n\n"
            + tweet_text
            + "\n\n"
            + "AI: Gemini\n"
            + "Karakter: "
            + str(len(tweet_text))
            + "\n\n"
            + "X paylasimi: Yapilmadi"
        )

        send_telegram_log(telegram_message)

        print()
        print("PROGRAM BASARIYLA TAMAMLANDI.")

        return 0

    except Exception as e:
        print()
        print("=" * 60)
        print("PROGRAM HATASI")
        print("=" * 60)
        print(str(e))
        print("=" * 60)

        send_telegram_log(
            "Doga botu hata verdi:\n\n" + str(e)
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
