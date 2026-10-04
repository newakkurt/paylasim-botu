import json
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


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

# Buffer ücretsiz API
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
BUFFER_URL = "https://api.buffer.com"

# Paylaşımdan kaç saniye sonra etkileşim hatırlatması gitsin (varsayılan 960 sn = 16 dk)
ENGAGE_DELAY_SEC = _env_int("ENGAGE_DELAY_SEC", 960)
# SKIP_WAIT=1 -> bekleme ve hatırlatma tamamen atlanır (test / manuel çalıştırma için)
SKIP_WAIT = _env_flag("SKIP_WAIT")
# ENABLE_TELEGRAM_POLL=1 -> script başlarken Telegram komutlarını kendisi okur.
# Aynı token'ı başka bir bot (Render) dinliyorsa AÇMA, güncellemeleri birbirinden çalar.
ENABLE_TELEGRAM_POLL = _env_flag("ENABLE_TELEGRAM_POLL")
# NATURE_MORNING_WEATHER=1 -> sabah 07-10 arası bu script hava durumu tweeti atar.
# Varsayılan KAPALI: hava durumu zaten weather_bot.py / "/hava" komutuyla paylaşılıyor.
NATURE_MORNING_WEATHER = _env_flag("NATURE_MORNING_WEATHER")

TZ = ZoneInfo("Europe/Istanbul")
X_LIMIT = 280

# --- HASHTAG GARANTİSİ VE ETKİLEŞİM HEDEFLERİ ---
DEFAULT_HASHTAGS = ["#Nature", "#Wildlife", "#Earth", "#NaturePhotography", "#Environment"]
TARGET_ACCOUNTS = ["NatGeo", "BBCEarth", "EarthPix", "ourplanet", "Discovery"]


def ensure_hashtags(text: str) -> str:
    found_tags = re.findall(r"#\w+", text)
    if len(found_tags) < 5:
        missing = [tag for tag in DEFAULT_HASHTAGS if tag not in found_tags]
        text += " " + " ".join(missing[: 5 - len(found_tags)])
    return text.strip()


def x_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def fit_for_x(text: str) -> str:
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


# --- 300'LÜK BİLGİ HAVUZU ---
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


# Tweet konuları: (AI'a verilecek konu tanımı, o konuya uygun görsel arama sorgusu)
TOPICS = {
    "animals": ("wild animals and wildlife", "wildlife animal nature"),
    "birds": ("wild birds", "wild bird nature"),
    "trees": ("forests and trees", "forest trees"),
    "ocean": ("oceans, seas and marine life", "ocean sea underwater"),
    "water": ("rivers, lakes and waterfalls", "waterfall river nature"),
    "plants": ("plants, flowers and botany", "wild flowers plants"),
    "insects": ("insects and pollinators", "insect macro nature"),
    "earth": ("mountains, volcanoes and natural landscapes", "mountain landscape"),
    "weather": ("weather, clouds and the sky", "dramatic sky clouds"),
    "fungi": ("mushrooms and fungi", "mushrooms forest"),
}
# Vahşi yaşam, orman ve okyanus daha sık çıksın diye iki kez listelendi
TOPIC_POOL = ["animals", "animals", "trees", "trees", "ocean", "ocean",
              "birds", "water", "plants", "insects", "earth", "weather", "fungi"]


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
    pool = load_fact_pool()
    if not pool:
        return random.choice(FALLBACK_NOTES)
    now = datetime.now(TZ)
    idx = (now.toordinal() * 2 + (1 if now.hour >= 16 else 0)) % len(pool)
    cat, fact = pool[idx]
    tags = " ".join(CATEGORY_TAGS.get(cat, ["#Nature"]))
    return ensure_hashtags(f"{fact} {tags}")


def notify_telegram(message_text: str):
    """Telegram'a mesaj yollar. Markdown ayrıştırılamazsa düz metinle tekrar dener,
    böylece tweet içindeki _ veya * gibi karakterler bildirimi sessizce öldürmez."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message_text[:4096]}
    try:
        res = requests.post(url, data={**payload, "parse_mode": "Markdown"}, timeout=10)
        if res.status_code != 200:
            print(f"Telegram Markdown hatası {res.status_code}: {res.text[:150]} -> düz metin deneniyor")
            requests.post(url, data=payload, timeout=10)
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


def call_llms(prompt: str):
    generated = None
    if GEMINI_API_KEY:
        for attempt in range(1, 4):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                if res.status_code == 200:
                    generated = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    break
                print(f"Gemini deneme {attempt}/3 HTTP {res.status_code}: {res.text[:150]}")
                if res.status_code not in (429, 500, 502, 503, 504):
                    break
            except Exception as e:
                print(f"Gemini Hatası (deneme {attempt}/3): {e}")
            time.sleep(3 * attempt)

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

    return generated


def generate_ai_text(prompt: str) -> str:
    generated = call_llms(prompt) or pick_pool_note()
    generated = generated.strip().strip('"').strip()
    return fit_for_x(ensure_hashtags(generated))


QUESTION_BANK = {
    "trees": [
        "Which tree would you most like to stand beneath: a giant redwood or an ancient bristlecone pine? 🌲",
        "If trees could talk, what do you think they would say about the forest around them? 🌳",
    ],
    "ocean": [
        "What do you think is the most amazing creature hiding in the deep sea? 🌊",
        "If you could dive anywhere in the world's oceans, where would you go? 🐠",
    ],
    "animals": [
        "Which wild animal do you think is the most underrated? 🦥",
        "If you could spend one day with any wild animal, which would you pick? 🐾",
    ],
    "generic": [
        "What is the most surprising thing you have learned about nature? 🌿",
        "Where do you feel most connected to nature? 🌍",
    ],
}


def guess_category(text: str):
    for cat, tags in CATEGORY_TAGS.items():
        if tags[0] in text:
            return cat
    return None


def generate_question(tweet_text: str) -> str:
    prompt = (
        "Here is a tweet:\n\n" + tweet_text + "\n\n"
        "Write ONE short follow-up question (max 140 characters) about the same topic as this tweet. "
        "It must spark curiosity and invite people to reply. "
        "No hashtags, no quotation marks, no preamble. Output only the question."
    )
    q = call_llms(prompt)
    if q:
        lines = q.strip().strip('"').strip().splitlines()
        q = re.sub(r"#\w+", "", lines[0]).strip().strip('"').strip() if lines else ""
        if "?" in q and 10 <= len(q) <= 200:
            return fit_for_x(q)
    bank = QUESTION_BANK.get(guess_category(tweet_text)) or QUESTION_BANK["generic"]
    return random.choice(bank)

# --- MEDYA ÇEKME İŞLEMLERİ (VİDEO VE RESİM) ---

def fetch_hd_video_url(query: str = "nature landscape") -> str:
    """Pexels API üzerinden HD MP4 Video arar."""
    if PEXELS_API_KEY:
        try:
            res = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": 10, "orientation": "landscape"},
                timeout=10,
            )
            if res.status_code == 200:
                videos = res.json().get("videos", [])
                if videos:
                    chosen = random.choice(videos)
                    for vf in chosen.get("video_files", []):
                        if vf.get("file_type") == "video/mp4" and vf.get("quality") == "hd":
                            return vf.get("link")
                    if chosen.get("video_files"):
                        return chosen["video_files"][0].get("link")
        except Exception as e:
            print(f"Pexels Video hatası: {e}")
    return None

def fetch_hd_image_url(query: str = "nature landscape"):
    if UNSPLASH_ACCESS_KEY:
        try:
            res = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"query": query, "orientation": "landscape", "client_id": UNSPLASH_ACCESS_KEY},
                timeout=10,
            )
            if res.status_code == 200:
                data = res.json()
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


# --- BUFFER (GraphQL) ---
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


def create_buffer_post(channel_id: str, text: str, image_url=None, reply=None) -> str:
    due = (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    assets = ""
def create_buffer_post(channel_id: str, text: str, media_url=None, is_video=False, reply=None) -> str:
    due = (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    assets = ""
    metadata = ""

    # BU SATIR EKLENDİ: Video ise GraphQL nesnesi 'video', resim ise 'image' olur
    media_asset_key = "video" if is_video else "image"

    if reply:
        first = "{ text: %s" % json.dumps(text, ensure_ascii=False)
        if media_url:
            # BU SATIR GÜNCELLENDİ: media_asset_key kullanılıyor
            first += f" assets: [{{ {media_asset_key}: {{ url: %s }} }}]" % json.dumps(media_url)
        first += " }"
        second = "{ text: %s }" % json.dumps(reply, ensure_ascii=False)
        metadata = "metadata: { twitter: { thread: [ %s %s ] } }" % (first, second)
    elif media_url:
        # BU SATIR GÜNCELLENDİ: media_asset_key kullanılıyor
        assets = f"assets: [{{ {media_asset_key}: {{ url: %s }} }}]" % json.dumps(media_url)

    mutation = """
    mutation {
      createPost(input: {
        text: %s
        channelId: %s
        schedulingType: automatic
        mode: customScheduled
        dueAt: "%s"
        %s
        %s
      }) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """ % (json.dumps(text, ensure_ascii=False), json.dumps(channel_id), due, assets, metadata)

    result = gql(mutation)["createPost"]
    if "post" in result and result["post"]:
        return result["post"]["id"]
    raise RuntimeError(result.get("message", "Bilinmeyen Buffer hatası"))
    
    metadata = ""
    if reply:
        first = "{ text: %s" % json.dumps(text, ensure_ascii=False)
        if image_url:
            first += " assets: [{ image: { url: %s } }]" % json.dumps(image_url)
        first += " }"
        second = "{ text: %s }" % json.dumps(reply, ensure_ascii=False)
        metadata = "metadata: { twitter: { thread: [ %s %s ] } }" % (first, second)
    elif image_url:
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
        %s
      }) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """ % (json.dumps(text, ensure_ascii=False), json.dumps(channel_id), due, assets, metadata)

    result = gql(mutation)["createPost"]
    if "post" in result and result["post"]:
        return result["post"]["id"]
    raise RuntimeError(result.get("message", "Bilinmeyen Buffer hatası"))


def post_to_x(text: str, media_url=None, is_video=False, reply=None): # is_video eklendi
    if not BUFFER_API_KEY:
        return False, "BUFFER_API_KEY eksik.", False
    try:
        channel_id = get_x_channel_id()
        attempts = []
        if reply:
            attempts.append((media_url, reply))
        attempts.append((media_url, None))
        if media_url:
            attempts.append((None, None))

        last_error = None
        for med, rp in attempts:
            try:
                # BU SATIR GÜNCELLENDİ: is_video parametresi aktarılıyor
                post_id = create_buffer_post(channel_id, text, med, is_video=is_video, reply=rp)
                print(f"✅ Buffer'a eklendi. Post ID: {post_id} | Video: {is_video} | yorum: {bool(rp)}")
                return True, "OK", bool(rp)
            except RuntimeError as e:
                print(f"Deneme başarısız: {e}")
                last_error = e
        raise last_error
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}", False


# --- TELEGRAM KOMUT HANDLERLARI ---
def send_telegram_help():
    """/yardim komutu çağrıldığında yönlendirme metnini iletir."""
    help_text = (
        "📖 *DOĞA BOTU YARDIM VE KOMUT REHBERİ*\n\n"
        "🤖 *Bot Nasıl Çalışır?*\n"
        "• Bot otomatik saatlerde Gemini/Groq/OpenRouter AI kullanarak doğa ile ilgili tweetler üretir.\n"
        "• Görseller Unsplash/Pexels HD kütüphanelerinden çekilir.\n"
        "• Tweet ve altında otomatik soru-yorum Buffer üzerinden X'e iletilir.\n\n"
        "⚡ *Mevcut Komutlar:*\n"
        "• `/paylas` : Hemen bir tweet hazırlar ve Buffer'a ekler.\n"
        "• `/etkilesim` : Canlı linkler, tek dokunuşla takip bağlantıları ve hazır akıllı yorum üretir.\n"
        "• `/yardim` : Bu yardım rehberini gösterir.\n\n"
        "🛡️ *Neden API Kredisi Harcanmaz?*\n"
        "Paylaşımlar Buffer API üzerinden yapıldığı için hesabın X API sınırlarına takılmaz ve tamamen ücretsizdir."
    )
    notify_telegram(help_text)


def send_interaction_reminder(tweet_text: str = None):
    """/etkilesim komutu çağrıldığında veya paylaşımdan sonra gecikmeyle tetiklenir.
    Beğeni/takip ELLE yapılır; bot sadece hazır yorum ve tek dokunuşluk linkleri verir."""
    context = tweet_text if tweet_text else "Nature, wildlife, and serene natural landscapes"

    prompt = (
        f"Generate a thoughtful, engaging, short comment (max 100 chars) that I can post on other popular nature tweets. "
        f"Topic context: '{context[:100]}'. Do not use hashtags."
    )
    suggested_comment = call_llms(prompt) or "Incredible capture! Nature never ceases to amaze us. 🌿"
    suggested_comment = suggested_comment.strip().strip('"').strip().replace("`", "'")

    targets = random.sample(TARGET_ACCOUNTS, k=min(3, len(TARGET_ACCOUNTS)))
    follow_lines = "\n".join(f"• [@{a}](https://x.com/intent/follow?screen_name={a})" for a in targets)

    reminder_msg = (
        "🚀 *YARI OTOMATİK ETKİLEŞİM MODÜLÜ*\n\n"
        f"💡 *Önerilen Akıllı Yorum:*\n`{suggested_comment}`\n\n"
        "1️⃣ *Canlı Doğa Akışı:*\n🔗 [Canlı #Nature Tweetleri](https://x.com/search?q=%23Nature%20OR%20%23Wildlife%20min_faves%3A10&f=live)\n"
        "_(İlk 2-3 tweet'i beğen ve yukarıdaki yorumu yap)_\n\n"
        "2️⃣ *Tek Dokunuşla Takip (onay ekranı açılır):*\n"
        f"{follow_lines}\n\n"
        "⏱️ _Süre: ~30 saniye. Beğeni ve takip elle yapıldığı için otomasyon kaynaklı hesap riski yok._"
    )
    notify_telegram(reminder_msg)


def check_telegram_updates():
    """OPSİYONEL (ENABLE_TELEGRAM_POLL=1): script çalışırken bekleyen /etkilesim ve /yardim komutlarını işler."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            updates = res.json().get("result", [])
            for update in updates:
                msg = update.get("message", {})
                text = msg.get("text", "").strip().lower()
                if text in ["/etkilesim", "/etkileşim"]:
                    send_interaction_reminder()
                elif text in ["/yardim", "/yardım"]:
                    send_telegram_help()
            if updates:
                # İşlenen güncellemeleri onayla, bir sonraki çalışmada tekrar gelmesin
                last_id = updates[-1]["update_id"]
                requests.get(url, params={"offset": last_id + 1}, timeout=5)
    except Exception as e:
        print(f"Telegram komut okuma hatası: {e}")


def run_job(wait: bool = True, background_reminder: bool = False) -> bool:
    hour = datetime.now(TZ).hour

    if NATURE_MORNING_WEATHER and 7 <= hour < 10:
        text = get_weather_info()
        # BU SATIR GÜNCELLENDİ
        media_url = fetch_hd_video_url("morning sunrise nature") or fetch_hd_image_url("morning sunrise nature")
        is_video = True if media_url and ".mp4" in media_url.lower() else False
        title = "☀️ Sabah Hava Durumu Buffer'a eklendi"
        err_title = "❌ Hava Durumu Hata:"
    else:
        ctx = get_season_context()
        cat = random.choice(TOPIC_POOL)
        topic, query = TOPICS[cat]
        tags = " ".join(CATEGORY_TAGS.get(cat, ["#Nature"]))

        # BU BLOK EKLENDİ: Önce video aranır, bulunamazsa resme geçilir
        media_url = fetch_hd_video_url(query)
        is_video = True if media_url else False

        if not media_url:
            media_url = fetch_hd_image_url(query)
            is_video = False

        prompt = (
            f"Write an engaging English tweet containing ONE surprising, true and well-established fact about {topic}. "
            "Only state facts you are sure about and do not invent numbers. "
            f"Seasonal context (use only if it fits naturally): {ctx}. "
            "Max 230 characters in total including hashtags. "
            f"End with these hashtags plus 1-2 more relevant ones: {tags}. "
            "Output only the tweet text, no quotes, no preamble."
        )
        text = generate_ai_text(prompt)
        
        # BU SATIRLAR GÜNCELLENDİ
        media_type = "🎥 Video" if is_video else "📸 Görsel"
        title = f"{media_type} İçerik ({cat}) Buffer'a eklendi"
        err_title = "❌ Paylaşım Hatası:"

    question = generate_question(text)
    # BU SATIR GÜNCELLENDİ: is_video iletiliyor
    success, reason, replied = post_to_x(text, media_url, is_video=is_video, reply=question)

    if success:
        msg = f"{title}\n\n{text}\n\n💬 Yorum: {question}"
        if not replied:
            msg += "\n\n⚠️ Yorum eklenemedi, sadece ana tweet gitti (loga bak)."
        notify_telegram(msg)

        if SKIP_WAIT or ENGAGE_DELAY_SEC <= 0:
            print("⏭️ Etkileşim hatırlatması atlandı (SKIP_WAIT / ENGAGE_DELAY_SEC).")
        elif wait:
            minutes = ENGAGE_DELAY_SEC // 60
            print(f"⏳ Paylaşım yapıldı. Etkileşim bildirimi için {minutes} dk bekleniyor...")
            time.sleep(ENGAGE_DELAY_SEC)
            send_interaction_reminder(text)
            print("✅ Yarı otomatik etkileşim bildirimi Telegram'a gönderildi.")
        elif background_reminder:
            timer = threading.Timer(ENGAGE_DELAY_SEC, send_interaction_reminder, args=(text,))
            timer.daemon = True
            timer.start()
            print(f"⏳ Etkileşim hatırlatması {ENGAGE_DELAY_SEC // 60} dk sonra için zamanlandı.")
        return True

    notify_telegram(f"{err_title} {reason}")
    print(reason)
    return False


if __name__ == "__main__":
    if ENABLE_TELEGRAM_POLL:
        check_telegram_updates()
    sys.exit(0 if run_job() else 1)
