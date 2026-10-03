import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

# --- ENV VARIABLES ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or "meta-llama/llama-3.3-70b-instruct:free"
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Buffer ücretsiz API (X'e paylaşımı Buffer yapıyor, X API kredisi gerekmiyor)
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")  # opsiyonel, boşsa otomatik bulunur
BUFFER_URL = "https://api.buffer.com"

TZ = ZoneInfo("Europe/Istanbul")
X_LIMIT = 280

# --- HASHTAG GARANTİSİ ---
DEFAULT_HASHTAGS = ["#Nature", "#Wildlife", "#Earth", "#NaturePhotography", "#Environment"]


def ensure_hashtags(text: str) -> str:
    found_tags = re.findall(r"#\w+", text)
    if len(found_tags) < 5:
        missing = [tag for tag in DEFAULT_HASHTAGS if tag not in found_tags]
        text += " " + " ".join(missing[: 5 - len(found_tags)])
    return text.strip()


def x_length(text: str) -> int:
    # UTF-16 birimi: emoji = 2, düz harf = 1 (X'in sayımına yakın)
    return len(text.encode("utf-16-le")) // 2


def fit_for_x(text: str) -> str:
    """280 karakteri aşarsa önce sondaki hashtag'leri atar, yetmezse keser."""
    text = text.strip()
    while x_length(text) > X_LIMIT:
        m = re.search(r"\s+#\w+\s*$", text)
        if not m:
            break
        text = text[: m.start()].rstrip()
    if x_length(text) > X_LIMIT:
        while x_length(text) > X_LIMIT - 1:
            text = text[:-1]
        text = text.rstrip() + "…"
    return text


# --- YEDEK İÇERİK HAVUZU ---
FALLBACK_NOTES = [
    "Did you know? Trees in a forest can communicate and share nutrients through an underground fungal network. #NatureFacts #ForestLife #Trees #MotherNature #EcoSystem",
    "Bananas are naturally slightly radioactive because they contain high levels of potassium. #Science #Nature #ScienceFacts #Biology #NatureWonders",
    "Honey never spoils. Archeologists have found 3,000-year-old honey in ancient Egyptian tombs. #NatureMagic #Honey #History #AncientEgypt #FoodFacts",
    "A single full-grown oak tree can absorb up to 50 gallons of water per day. #Trees #Environment #Forests #SaveTrees #GreenPlanet",
    "Clouds look light and fluffy, but an average cumulus cloud weighs about 1.1 million pounds! #Weather #Nature #Atmosphere #Sky #NatureFacts",
]


# --- 300'LÜK BİLGİ HAVUZU (nature_facts.txt, satır formatı: kategori|bilgi) ---
CATEGORY_TAGS = {
    "trees": ["#Trees", "#Forest", "#TreeFacts", "#Nature"],
    "ocean": ["#Ocean", "#MarineLife", "#OceanFacts", "#Nature"],
    "animals": ["#Animals", "#Wildlife", "#AnimalFacts", "#Nature"],
    "birds": ["#Birds", "#Birdwatching", "#BirdFacts", "#Nature"],
    "insects": ["#Insects", "#Bugs", "#NatureFacts", "#Nature"],
    "weather": ["#Weather", "#Sky", "#NatureFacts", "#Nature"],
    "earth": ["#Earth", "#Geology", "#EarthFacts", "#Nature"],
    "plants": ["#Plants", "#Botany", "#PlantFacts", "#Nature"],
    "fungi": ["#Fungi", "#Mushrooms", "#NatureFacts", "#Nature"],
    "water": ["#Water", "#Rivers", "#NatureFacts", "#Nature"],
    "space": ["#Space", "#Astronomy", "#Cosmos", "#Nature"],
    "seasons": ["#Seasons", "#Wildlife", "#NatureFacts", "#Nature"],
}


def load_fact_pool():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nature_facts.txt")
    pool = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "|" not in line:
                    continue
                cat, fact = line.split("|", 1)
                pool.append((cat.strip().lower(), fact.strip()))
    except OSError as e:
        print(f"Havuz dosyası okunamadı: {e}")
    return pool


def pick_pool_note() -> str:
    """Tüm LLM'ler patlarsa havuzdan seç. Güne ve saate göre sıralı gider, tekrar etmez."""
    pool = load_fact_pool()
    if not pool:
        return random.choice(FALLBACK_NOTES)
    now = datetime.now(TZ)
    idx = (now.toordinal() * 2 + (1 if now.hour >= 16 else 0)) % len(pool)
    cat, fact = pool[idx]
    tags = " ".join(CATEGORY_TAGS.get(cat, ["#Nature"]))
    return ensure_hashtags(f"{fact} {tags}")


def notify_telegram(message_text: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message_text},
            timeout=10,
        )
    except Exception as e:
        print(f"Telegram bildirim hatası: {e}")


def get_season_context() -> str:
    month = datetime.now(TZ).month
    if month in [12, 1, 2]:
        return "Winter (serene snow, calm forests)"
    elif month in [3, 4, 5]:
        return "Spring (fresh flowers, rebirth)"
    elif month in [6, 7, 8]:
        return "Summer (golden sunlight, warm oceans)"
    return "Autumn (golden leaves, misty mornings)"


def generate_ai_text(prompt: str) -> str:
    generated = None
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if res.status_code == 200:
                generated = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                print(f"Gemini HTTP {res.status_code}: {res.text[:150]}")
        except Exception as e:
            print(f"Gemini Hatası: {e}")

    if not generated and GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                generated = res.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"Groq HTTP {res.status_code}: {res.text[:150]}")
        except Exception as e:
            print(f"Groq Hatası: {e}")

    if not generated and OPENROUTER_API_KEY:
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
                timeout=30,
            )
            if res.status_code == 200:
                generated = res.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"OpenRouter HTTP {res.status_code}: {res.text[:150]}")
        except Exception as e:
            print(f"OpenRouter Hatası: {e}")

    if not generated:
        generated = pick_pool_note()

    generated = generated.strip().strip('"').strip()
    return fit_for_x(ensure_hashtags(generated))


def fetch_hd_image_url(query: str = "nature landscape"):
    """Görseli indirmiyoruz; Buffer herkese açık doğrudan URL istiyor."""
    if UNSPLASH_ACCESS_KEY:
        try:
            res = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"query": query, "orientation": "landscape", "client_id": UNSPLASH_ACCESS_KEY},
                timeout=10,
            )
            if res.status_code == 200:
                data = res.json()
                # Unsplash kuralı: kullanım sayacı için download endpoint'ine ping
                try:
                    dl = data.get("links", {}).get("download_location")
                    if dl:
                        requests.get(dl, params={"client_id": UNSPLASH_ACCESS_KEY}, timeout=5)
                except Exception:
                    pass
                return data["urls"]["regular"]
        except Exception as e:
            print(f"Unsplash hatası: {e}")

    if PEXELS_API_KEY:
        try:
            res = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": 10},
                timeout=10,
            )
            if res.status_code == 200:
                photos = res.json().get("photos", [])
                if photos:
                    return random.choice(photos)["src"]["large2x"]
        except Exception as e:
            print(f"Pexels hatası: {e}")

    return None


def get_weather_info() -> str:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast?latitude=41.0082&longitude=28.9784"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Europe%2FIstanbul"
        )
        res = requests.get(url, timeout=10).json()
        max_t = res["daily"]["temperature_2m_max"][0]
        min_t = res["daily"]["temperature_2m_min"][0]
        text = (
            f"Good morning! Today in Istanbul: High of {max_t}°C, Low of {min_t}°C. "
            "Embrace nature! ☀️🌿 #Weather #Nature #Istanbul #GoodMorning #NatureVibes"
        )
    except Exception:
        text = "Good morning! Wishing you a peaceful and nature-filled day ahead! 🌿 #Nature #MorningVibes #Peaceful #GreenPlanet #Earth"
    return fit_for_x(ensure_hashtags(text))


# --- BUFFER (GraphQL, ücretsiz plan) ---
def gql(query: str) -> dict:
    res = requests.post(
        BUFFER_URL,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {BUFFER_API_KEY}"},
        json={"query": query},
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Buffer HTTP {res.status_code}: {res.text[:150]}")
    body = res.json()
    if body.get("errors"):
        raise RuntimeError(f"Buffer GraphQL: {str(body['errors'])[:200]}")
    return body["data"]


def get_x_channel_id() -> str:
    if BUFFER_CHANNEL_ID:
        return BUFFER_CHANNEL_ID

    orgs = gql("query { account { organizations { id name } } }")["account"]["organizations"]
    seen = []
    for org in orgs:
        q = "query { channels(input: {organizationId: %s}) { id name service } }" % json.dumps(org["id"])
        for ch in gql(q)["channels"]:
            service = str(ch.get("service", "")).lower()
            seen.append(service)
            if service in ("twitter", "x"):
                return ch["id"]
    raise RuntimeError(f"Buffer'da bağlı X kanalı bulunamadı. Görülen kanallar: {seen or 'hiç'}")


def create_buffer_post(channel_id: str, text: str, image_url=None) -> str:
    # 3 dk sonrasına zamanla: Buffer'ın kuyruk saatlerine bağımlı kalmaz
    due = (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    assets = ""
    if image_url:
        assets = "assets: [{ image: { url: %s } }]" % json.dumps(image_url)
    mutation = """
    mutation {
      createPost(input: {
        text: %s
        channelId: %s
        schedulingType: automatic
        mode: customScheduled
        dueAt: "%s"
        %s
      }) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """ % (json.dumps(text, ensure_ascii=False), json.dumps(channel_id), due, assets)

    result = gql(mutation)["createPost"]
    if "post" in result and result["post"]:
        return result["post"]["id"]
    raise RuntimeError(result.get("message", "Bilinmeyen Buffer hatası"))


def post_to_x(text: str, image_url=None):
    if not BUFFER_API_KEY:
        return False, "BUFFER_API_KEY eksik."
    try:
        channel_id = get_x_channel_id()
        try:
            post_id = create_buffer_post(channel_id, text, image_url)
        except RuntimeError as e:
            # Görsel yüzünden patladıysa metin-only dene
            if image_url:
                print(f"Görselli paylaşım başarısız ({e}); görselsiz deneniyor.")
                post_id = create_buffer_post(channel_id, text, None)
            else:
                raise
        print(f"✅ Buffer'a eklendi (3 dk içinde X'e çıkar). Post ID: {post_id}")
        return True, "OK"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def run_job():
    hour = datetime.now(TZ).hour

    if 7 <= hour < 10:
        text = get_weather_info()
        img = fetch_hd_image_url("morning sunrise nature")
        title = "☀️ Sabah Hava Durumu Paylaşıldı!"
        err_title = "❌ Hava Durumu Hata:"
    else:
        ctx = get_season_context()
        prompt = (
            f"Write a beautiful English tweet about nature. Context: {ctx}. "
            "Max 180 chars. Include at least 5 relevant hashtags. Output only the tweet text."
        )
        text = generate_ai_text(prompt)
        img = fetch_hd_image_url("scenic nature landscape")
        title = "📸 Görsel İçerik Paylaşıldı!"
        err_title = "❌ Paylaşım Hatası:"

    success, reason = post_to_x(text, img)
    if success:
        notify_telegram(f"{title}\n\n{text}")
    else:
        notify_telegram(f"{err_title} {reason}")
        print(reason)
        sys.exit(1)


if __name__ == "__main__":
    run_job()
