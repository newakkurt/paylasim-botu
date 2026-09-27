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

BASE_HASHTAGS = "#doğa #nature #earth"

# 1. Uluslararası Doğa ve Çevre Günleri Takvimi (Ay, Gün)
SPECIAL_ENVIRONMENTAL_DAYS = {
    (3, 3): ("Dünya Yaban Hayatı Günü", "#DünyaYabanHayatıGünü", "yaban hayatı ve koruma altındaki canlı türleri"),
    (3, 21): ("Dünya Ormancılık Günü", "#DünyaOrmancılıkGünü", "dünyanın ormanları ve ağaçların hayati önemi"),
    (3, 22): ("Dünya Su Günü", "#DünyaSuGünü", "su kaynakları, nehirler ve su ekosistemleri"),
    (4, 22): ("Dünya Günü (Earth Day)", "#DünyaGünü #EarthDay", "gezegenimizin ekosistemi ve doğayı koruma bilinci"),
    (5, 20): ("Dünya Arı Günü", "#DünyaArıGünü", "arılar, tozlaşma ve yaşamın devamındaki kritik rolleri"),
    (5, 22): ("Dünya Biyoçeşitlilik Günü", "#BiyoçeşitlilikGünü", "gezegenimizdeki canlı türlerinin zenginliği"),
    (6, 5): ("Dünya Çevre Günü", "#DünyaÇevreGünü", "çevre bilinci ve doğanın korunması"),
    (6, 8): ("Dünya Okyanus Günü", "#DünyaOkyanusGünü", "okyanuslar, denizler ve su altı yaşamı"),
    (10, 4): ("Dünya Hayvanları Koruma Günü", "#DünyaHayvanlarıKorumaGünü", "hayvanlar alemi ve onları koruma çabaları"),
    (12, 11): ("Dünya Dağ Günü", "#DünyaDağGünü", "dağlar, yüksek ekosistemler ve dağ yaşamı"),
}

# 2. Haftanın Günlerine Özel Konseptler
WEEKDAY_CONCEPTS = {
    0: ("Dev Ağaçlar ve Ormanlar", "#ForestMonday", ["forest", "trees", "woodland"]),
    1: ("Büyüleyici Bitkiler ve Mantarlar", "#PlantTuesday", ["plants", "flowers", "mushrooms"]),
    2: ("Yaban Hayatı ve Doğa Canlıları", "#WildlifeWednesday", ["wildlife", "animals", "jungle"]),
    3: ("Dağlar, Vadiler ve Doğal Oluşumlar", "#EarthThursday", ["mountains", "canyon", "valley"]),
    4: ("Okyanuslar, Denizler ve Su Altı", "#OceanFriday", ["ocean", "underwater", "sea"]),
    5: ("Kuşlar ve Gökyüzü Canlıları", "#SkySaturday", ["birds", "eagle", "flying"]),
    6: ("Biyoçeşitlilik ve Ekosistemler", "#NatureSunday", ["nature", "rainforest", "landscape"]),
}


def get_seasonal_keywords() -> list[str]:
    """Aya göre mevsimsel Unsplash kelimelerini döndürür."""
    month = datetime.now().month
    if month in (12, 1, 2):
        return ["winter", "snow"]
    elif month in (3, 4, 5):
        return ["spring", "bloom"]
    elif month in (6, 7, 8):
        return ["summer", "green"]
    else:
        return ["autumn", "fall"]


def get_today_topic_and_hashtags() -> tuple[str, str, list[str]]:
    """Günün özel çevre günü veya haftalık konsept durumunu belirler."""
    now = datetime.now()
    today_key = (now.month, now.day)

    # Özel Çevre Günü Kontrolü
    if today_key in SPECIAL_ENVIRONMENTAL_DAYS:
        event_name, hashtag, focus = SPECIAL_ENVIRONMENTAL_DAYS[today_key]
        print(f"🎉 Özel Gün Algılandı: {event_name}")
        full_hashtags = f"{hashtag} {BASE_HASHTAGS}"
        prompt_instruction = f"Bugün {event_name}! Özellikle {focus} hakkında ilginç, etkileyici ve bugünün anlam ve önemine uygun bir bilgi yaz."
        search_keywords = ["nature", "environment"]
        return prompt_instruction, full_hashtags, search_keywords

    # Haftalık Günlük Konsept Kontrolü
    weekday = now.weekday()
    concept_name, concept_hashtag, concept_keywords = WEEKDAY_CONCEPTS[weekday]
    print(f"📅 Günlük Konsept Algılandı ({now.strftime('%A')}): {concept_name}")
    full_hashtags = f"{concept_hashtag} {BASE_HASHTAGS}"
    prompt_instruction = f"Bugünün teması '{concept_name}'. Özellikle bu konu hakkında ilginç, az bilinen bir bilgi yaz."
    
    return prompt_instruction, full_hashtags, concept_keywords


def generate_nature_fact(prompt_instruction: str) -> str:
    """Google Gemini API kullanarak gemini-3.8-flash modeli ile içerik üretir."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        f"{prompt_instruction}\n"
        "Bilginin hemen ardından takipçilerin yorum yazmasını sağlayacak tatlı, samimi ve merak uyandırıcı kısa bir soru ekle "
        "(Örnek: 'Siz hayatınızda gördüğünüz en yaşlı ağacı hatırlıyor musunuz? 🌿'). "
        "Direkt metinle başla. Giriş/çıkış açıklaması yapma, tırnak işareti veya 'İşte bilgi:' gibi ifadeler kullanma. "
        "Toplam uzunluk maksimum 220 karakter olsun."
    )

    model_name = "gemini-3.8-flash"

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


def fetch_unsplash_photo(query_str: str) -> dict:
    """Unsplash API'sinden fotoğraf verisini çeker."""
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": query_str, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_unsplash_image_url(concept_keywords: list[str]) -> str:
    """Arama terimini basitleştirerek Unsplash'ten görsel çeker; hata durumunda varsayılan aramaya geçer."""
    selected_concept = random.choice(concept_keywords)
    selected_season = random.choice(get_seasonal_keywords())
    
    query_candidates = [
        f"{selected_season} {selected_concept}",
        selected_concept,
        "nature"
    ]

    for query_str in query_candidates:
        try:
            print(f"Unsplash araması deneniyor: '{query_str}'")
            data = fetch_unsplash_photo(query_str)
            return data["urls"]["regular"]
        except Exception as e:
            print(f"Unsplash sorgusu hatası ('{query_str}'): {e}. Yedek sorguya geçiliyor...")
            time.sleep(1)

    raise RuntimeError("Unsplash API hiçbir arama sorgusuna görsel döndüremedi.")


def send_telegram_notification(text: str, image_url: str) -> None:
    """Paylaşım başarılı olduğunda Telegram'a bildirim atar."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    caption = f"✅ **Yeni X (Twitter) Paylaşımı Yapıldı!**\n\n{text}"

    try:
        requests.post(
            telegram_url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        print("Telegram başarı bildirimi gönderildi!")
    except Exception as e:
        print(f"Telegram bildirim hatası: {e}")


def send_telegram_error(error_message: str) -> None:
    """Hata durumunda Telegram'a otomatik kırmızı uyarı gönderir."""
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
    raise RuntimeError("Buffer hesabında bağlı bir X/Twitter kanalı bulunamadı.")


def create_post(channel_id: str, text: str, image_url: str) -> None:
    """Buffer üzerinden X gönderisi paylaşımı yapar."""
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

        # 1. Bugünün konseptini / özel gününü ve hashtag'lerini belirle
        prompt_instruction, hashtags, concept_keywords = get_today_topic_and_hashtags()

        # 2. Gemini-3.8-flash ile metin üret
        fact = generate_nature_fact(prompt_instruction)
        text = fact + "\n\n" + hashtags

        # 3. Temaya ve mevsime uygun HD görsel çek
        image_url = get_unsplash_image_url(concept_keywords)

        # 4. Buffer üzerinden paylaş
        create_post(channel_id, text, image_url)

        # 5. Telegram Bildirimi
        send_telegram_notification(text, image_url)

    except Exception as e:
        error_msg = str(e)
        print(f"Kritik Hata: {error_msg}")
        send_telegram_error(error_msg)
        raise e


if __name__ == "__main__":
    main()
