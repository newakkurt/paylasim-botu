import os
import random
import time
import requests
from datetime import datetime
from google import genai

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Telegram Ayarları
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HASHTAGS = "#doğa #orman #nature #forest #earth"


def get_seasonal_keywords() -> list[str]:
    """Bulunulan aya göre mevsimsel Unsplash arama kelimelerini döndürür."""
    month = datetime.now().month

    if month in (12, 1, 2):  # Kış
        print("Mevsim Algılandı: Kış (Winter) görselleri seçiliyor...")
        return [
            "winter forest",
            "snowy trees",
            "frozen lake",
            "snow nature landscape",
            "pine trees snow",
        ]
    elif month in (3, 4, 5):  # İlkbahar
        print("Mevsim Algılandı: İlkbahar (Spring) görselleri seçiliyor...")
        return [
            "spring forest",
            "blooming trees",
            "cherry blossom nature",
            "fresh green forest",
            "spring wildflowers",
        ]
    elif month in (6, 7, 8):  # Yaz
        print("Mevsim Algılandı: Yaz (Summer) görselleri seçiliyor...")
        return [
            "summer forest",
            "tropical jungle",
            "sunny nature landscape",
            "lush green forest",
            "waterfall summer",
        ]
    else:  # Sonbahar (9, 10, 11)
        print("Mevsim Algılandı: Sonbahar (Autumn/Fall) görselleri seçiliyor...")
        return [
            "autumn forest",
            "fall foliage",
            "golden forest landscape",
            "yellow leaves forest",
            "misty autumn woods",
        ]


def generate_nature_fact() -> str:
    """Google Gemini API kullanarak bilgi ve etkileşim artırıcı soru üretir."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        "Doğa, ormanlar, bitkiler veya orman canlıları hakkında ilginç, az bilinen, merak uyandırıcı 1 adet Türkçe bilgi yaz. "
        "Bilginin hemen ardından takipçilerin yorum yazmasını sağlayacak tatlı, samimi ve merak uyandırıcı kısa bir soru ekle "
        "(Örnek: 'Siz hayatınızda gördüğünüz en yaşlı ağacı hatırlıyor musunuz? 🌿'). "
        "Direkt metinle başla. Giriş/çıkış açıklaması yapma, tırnak işareti veya 'İşte bilgi:' gibi ifadeler kullanma. "
        "Toplam uzunluk maksimum 230 karakter olsun."
    )

    models_to_try = ["gemini-3.8-flash"]

    for model_name in models_to_try:
        for attempt in range(3):
            try:
                print(f"Gemini isteği gönderiliyor: Model={model_name}, Deneme={attempt + 1}")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                print(f"Gemini API uyarısı ({model_name}): {e}")
                time.sleep(3)

    raise RuntimeError("Gemini API tüm denemelere rağmen yanıt veremedi.")


def send_telegram_notification(text: str, image_url: str) -> None:
    """Paylaşım yapıldığında Telegram hesabınıza bilgilendirme mesajı gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram ayarları eksik olduğu için bildirim atlandı.")
        return

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    caption = f"✅ **Yeni X (Twitter) Paylaşımı Yapıldı!**\n\n{text}"

    try:
        resp = requests.post(
            telegram_url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        resp.raise_for_status()
        print("Telegram başarı bildirimi gönderildi!")
    except Exception as e:
        print(f"Telegram bildirim hatası: {e}")


def send_telegram_error(error_message: str) -> None:
    """Hata durumunda Telegram hesabınıza otomatik uyarı mesajı gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = (
        "⚠️ **Doğa Botu Hata Bildirimi!**\n\n"
        "Sistem otomatik paylaşım yaparken bir sorunla karşılaştı.\n\n"
        f"**Hata Detayı:**\n`{error_message}`"
    )

    try:
        requests.post(
            telegram_url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        print("Hata bildirimi Telegram'a gönderildi.")
    except Exception as e:
        print(f"Hata bildirimi gönderilemedi: {e}")


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        BUFFER_API_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"Buffer API hatası: {data['errors']}")
    return data["data"]


def get_organization_id() -> str:
    data = buffer_graphql(
        "query GetOrganizations { account { organizations { id name } } }"
    )
    orgs = data["account"]["organizations"]
    if not orgs:
        raise RuntimeError("Buffer hesabında hiç organizasyon bulunamadı.")
    return orgs[0]["id"]


def get_twitter_channel_id(organization_id: str) -> str:
    data = buffer_graphql(
        """
        query GetChannels($organizationId: OrganizationId!) {
          channels(input: { organizationId: $organizationId }) {
            id
            name
            service
          }
        }
        """,
        {"organizationId": organization_id},
    )
    for ch in data["channels"]:
        if ch["service"] in ("twitter", "x"):
            return ch["id"]
    raise RuntimeError("Buffer hesabına bağlı bir X/Twitter kanalı bulunamadı.")


def get_unsplash_image_url() -> str:
    """Mevsime uygun kelimelerden birini seçerek HD fotoğraf çeker."""
    keywords = get_seasonal_keywords()
    selected_query = random.choice(keywords)
    print(f"Unsplash araması yapılıyor: '{selected_query}'")

    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": selected_query, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["urls"]["regular"]


def create_post(channel_id: str, text: str, image_url: str) -> None:
    data = buffer_graphql(
        """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post { id text dueAt }
            }
            ... on MutationError {
              message
            }
          }
        }
        """,
        {
            "input": {
                "text": text,
                "channelId": channel_id,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "assets": [{"image": {"url": image_url}}],
            }
        },
    )
    result = data["createPost"]
    if "message" in result:
        raise RuntimeError(f"Post oluşturulamadı: {result['message']}")
    print("Paylaşıldı:", result["post"])


def main() -> None:
    try:
        org_id = get_organization_id()
        channel_id = get_twitter_channel_id(org_id)

        # 1. Gemini ile etkileşim soruları içeren taze bilgi üretimi
        fact = generate_nature_fact()
        text = fact + "\n\n" + HASHTAGS

        # 2. Bulunulan mevsime uygun HD Unsplash görseli çekimi
        image_url = get_unsplash_image_url()

        # 3. Buffer üzerinden X (Twitter) paylaşımı
        create_post(channel_id, text, image_url)

        # 4. Telegram Başarı Bildirimi Gönderimi
        send_telegram_notification(text, image_url)

    except Exception as e:
        error_msg = str(e)
        print(f"Kritik Hata: {error_msg}")
        # Otomatik Hata Bildirimi Gönder
        send_telegram_error(error_msg)
        raise e


if __name__ == "__main__":
    main()
