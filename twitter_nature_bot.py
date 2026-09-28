import os
import random
import time
import requests
from datetime import datetime
from google import genai

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

BASE_HASHTAGS = "#doğa #nature #earth"

# Gemini başarısız olursa kullanılan ÜCRETSİZ yedek bilgi havuzu (hiçbir API/ücret gerektirmez)
FALLBACK_FACTS = [
    "Bir ağaç yılda ortalama 22 kilogram karbondioksit emer ve karşılığında oksijen üretir.",
    "Amazon Ormanları dünyadaki oksijenin yaklaşık %20'sini üretir, bu yüzden 'dünyanın akciğerleri' olarak anılır.",
    "Mantarlar, yer altında dev bir ağ oluşturarak ağaçların birbiriyle besin ve bilgi alışverişi yapmasını sağlar.",
    "Sekoya ağaçları 100 metreyi aşan boylara ulaşabilir ve 3000 yıldan fazla yaşayabilir.",
    "Bir meşe ağacı, yaşamı boyunca yaklaşık 10 milyon adet meşe palamudu üretebilir.",
    "Orman toprağının sadece bir avucunda, dünya nüfusundan daha fazla mikroorganizma bulunur.",
    "Kelebekler ayaklarıyla tat alır; bir çiçeğe konduklarında onu ayaklarıyla tadarlar.",
    "Baykuşlar boyunlarını 270 dereceye kadar çevirebilir çünkü göz küreleri hareket etmez.",
    "Bambü, dünyanın en hızlı büyüyen bitkisidir; bazı türleri günde 90 santimetre büyüyebilir.",
    "Bir karınca kendi ağırlığının 50 katına kadar yük taşıyabilir.",
    "Deniz otu çayırları, tropik yağmur ormanlarından bile daha hızlı karbon depolayabilir.",
    "Ağaçlar birbirlerine kimyasal sinyaller göndererek zararlı böcek saldırılarına karşı komşularını uyarabilir.",
    "Bal arıları, kovanlarına dönüş yolunu bulmak için Güneş'in konumunu pusula gibi kullanır.",
    "Kutup ayılarının derisi aslında siyahtır; kürkleri ışığı yansıttığı için beyaz görünür.",
    "Fillerin ayak tabanlarındaki hassas sinirler, kilometrelerce uzaktaki depremleri algılayabilir.",
    "Dünyadaki tüm canlı biyokütlenin yarısından fazlasını bitkiler oluşturur.",
    "Ahtapotlar üç kalbe sahiptir; ikisi solungaçlara, biri vücudun geri kalanına kan pompalar.",
    "Kunduzların yaptığı barajlar, zamanla küçük göller oluşturarak yüzlerce türe yaşam alanı sağlar.",
    "Yarasalar, tozlaşmadan tohum yayılımına kadar birçok tropik bitkinin hayatta kalması için kritik öneme sahiptir.",
    "Denizanaları 500 milyon yıldan uzun süredir var olan, dinozorlardan bile daha eski canlılardır.",
    "Bir tek balina, yaşamı boyunca karbondioksit tutma açısından binlerce ağaca bedel olabilir.",
    "Panda ayıları günde 12 saate kadar sadece bambu yiyerek geçirebilir.",
    "Mercan resifleri, okyanus tabanının yalnızca küçük bir kısmını kaplamasına rağmen deniz canlılarının çeyreğine ev sahipliği yapar.",
    "Bir çita, saatte 110 kilometreye kadar hız yapabilir ama bu hızı yalnızca birkaç saniye sürdürebilir.",
    "Bir semender, kopan bir uzvunu yeniden büyütebilir.",
    "Deniz kaplumbağaları, doğdukları plaja yıllar sonra yumurtlamak için geri dönebilir.",
    "Timsahlar, dişlerini yaşamları boyunca defalarca yenileyebilir.",
    "Ağustosböcekleri, toprak altında 17 yıla kadar larva olarak yaşayabilir.",
    "Yunuslar, birbirlerini tanımak için özel ıslık sesleri (imza ıslıkları) kullanır.",
    "Denizatları, yumurtaları erkek bireyin karnında taşıması ve doğurmasıyla hayvanlar aleminde eşsizdir.",
]

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
    now = datetime.now()
    today_key = (now.month, now.day)

    if today_key in SPECIAL_ENVIRONMENTAL_DAYS:
        event_name, hashtag, focus = SPECIAL_ENVIRONMENTAL_DAYS[today_key]
        print(f"🎉 Özel Gün Algılandı: {event_name}")
        full_hashtags = f"{hashtag} {BASE_HASHTAGS}"
        prompt_instruction = f"Bugün {event_name}! Özellikle {focus} hakkında ilginç, etkileyici ve bugünün anlam ve önemine uygun bir bilgi yaz."
        search_keywords = ["nature", "environment"]
        return prompt_instruction, full_hashtags, search_keywords

    weekday = now.weekday()
    concept_name, concept_hashtag, concept_keywords = WEEKDAY_CONCEPTS[weekday]
    print(f"📅 Günlük Konsept Algılandı ({now.strftime('%A')}): {concept_name}")
    full_hashtags = f"{concept_hashtag} {BASE_HASHTAGS}"
    prompt_instruction = f"Bugünün teması '{concept_name}'. Özellikle bu konu hakkında ilginç, az bilinen bir bilgi yaz."

    return prompt_instruction, full_hashtags, concept_keywords


def generate_with_groq(prompt: str) -> str:
    """Groq API ile dener (tamamen ücretsiz katman, kredi kartı gerektirmez)."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY tanımlanmamış.")

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def generate_nature_fact(prompt_instruction: str) -> str:
    """1. Gemini (ücretsiz), 2. Groq (ücretsiz), 3. sabit bilgi havuzu (ücretsiz)
    sırasıyla dener. Hiçbir aşamada ücretli bir servis kullanılmıyor."""
    prompt = (
        f"{prompt_instruction}\n"
        "Bilginin hemen ardından takipçilerin yorum yazmasını sağlayacak tatlı, samimi ve merak uyandırıcı kısa bir soru ekle "
        "(Örnek: 'Siz hayatınızda gördüğünüz en yaşlı ağacı hatırlıyor musunuz? 🌿'). "
        "Direkt metinle başla. Giriş/çıkış açıklaması yapma, tırnak işareti veya 'İşte bilgi:' gibi ifadeler kullanma. "
        "Toplam uzunluk maksimum 220 karakter olsun."
    )

    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
        model_name = "gemini-2.0-flash"
        for attempt in range(3):
            try:
                print(f"Gemini isteği gönderiliyor: Model={model_name}, Deneme={attempt + 1}")
                response = client.models.generate_content(model=model_name, contents=prompt)
                return response.text.strip()
            except Exception as e:
                print(f"Gemini API uyarısı ({model_name}): {e}")
                time.sleep(5)

    print("⚠️ Gemini yanıt veremedi. Groq API'ye geçiliyor (ücretsiz)...")
    try:
        return generate_with_groq(prompt)
    except Exception as e:
        print(f"Groq API uyarısı: {e}")

    print("⚠️ Groq da yanıt veremedi. Ücretsiz sabit bilgi havuzuna düşülüyor...")
    return random.choice(FALLBACK_FACTS)


def fetch_unsplash_photo(query_str: str) -> dict:
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": query_str, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_unsplash_image_url(concept_keywords: list[str]) -> str:
    selected_concept = random.choice(concept_keywords)
    selected_season = random.choice(get_seasonal_keywords())

    query_candidates = [
        f"{selected_season} {selected_concept}",
        selected_concept,
        "nature",
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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    caption = f"✅ **Yeni Paylaşım Yapıldı!**\n\n{text}"
    try:
        requests.post(
            telegram_url,
            json={"chat_id": TELEGRAM_CHAT_ID, "photo": image_url, "caption": caption, "parse_mode": "Markdown"},
            timeout=10,
        )
        print("Telegram başarı bildirimi gönderildi!")
    except Exception as e:
        print(f"Telegram bildirim hatası: {e}")


def send_telegram_error(error_message: str) -> None:
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
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        print("Hata bildirimi Telegram'a gönderildi.")
    except Exception as e:
        print(f"Hata bildirimi gönderilemedi: {e}")


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        BUFFER_API_URL,
        headers={"Authorization": f"Bearer {BUFFER_API_KEY}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"Buffer API hatası: {data['errors']}")
    return data["data"]


def get_organization_id() -> str:
    data = buffer_graphql("query GetOrganizations { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise RuntimeError("Buffer hesabında hiç organizasyon bulunamadı.")
    return orgs[0]["id"]


def get_channel_ids(organization_id: str) -> dict[str, str]:
    data = buffer_graphql(
        """
        query GetChannels($organizationId: OrganizationId!) {
          channels(input: { organizationId: $organizationId }) {
            id
            service
          }
        }
        """,
        {"organizationId": organization_id},
    )
    channels: dict[str, str] = {}
    for ch in data["channels"]:
        service = "twitter" if ch["service"] == "x" else ch["service"]
        channels[service] = ch["id"]
    return channels


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
        channels = get_channel_ids(org_id)

        prompt_instruction, hashtags, concept_keywords = get_today_topic_and_hashtags()
        fact = generate_nature_fact(prompt_instruction)
        text = fact + "\n\n" + hashtags
        image_url = get_unsplash_image_url(concept_keywords)

        if "twitter" in channels:
            create_post(channels["twitter"], text, image_url)
        else:
            print("Uyarı: Buffer'a bağlı bir X/Twitter kanalı bulunamadı, atlanıyor.")

        if "instagram" in channels:
            create_post(channels["instagram"], text, image_url)
        else:
            print("Uyarı: Buffer'a bağlı bir Instagram kanalı bulunamadı, atlanıyor.")

        send_telegram_notification(text, image_url)

    except Exception as e:
        error_msg = str(e)
        print(f"Kritik Hata: {error_msg}")
        send_telegram_error(error_msg)
        raise e


if __name__ == "__main__":
    main()
