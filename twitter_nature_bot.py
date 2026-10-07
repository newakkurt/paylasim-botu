import hashlib
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

# OPSİYONEL ve ÜCRETLİ: X API ile otomatik cevap. Anahtarları girmezsen hiç çalışmaz.
# (Ücretsiz alternatif: /cevap komutu veya --suggest, aşağıda.)
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

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

# POST_MODE: auto | series | random | quiz
#   auto   = 16:00 öncesi günün serisi; 16:00 sonrası Salı/Perşembe/Cumartesi quiz, diğer günler
#            eski usul rastgele konu
#   random = eski davranış (rastgele konu, hiçbir şey değişmedi)
POST_MODE = (os.getenv("POST_MODE") or "auto").strip().lower()
# Tekrar kontrolü HER ZAMAN açık. Aşağıdaki iki limit varsayılan KAPALI (0), istersen aç.
DAILY_MAX_POSTS = _env_int("DAILY_MAX_POSTS", 0)  # günlük en fazla paylaşım (0 = sınırsız)
MIN_GAP_MIN = _env_int("MIN_GAP_MIN", 0)          # iki paylaşım arası en az dakika (0 = kapalı)
# Quiz cevabı kaç dakika sonra ayrı tweet olarak yayınlansın
QUIZ_ANSWER_DELAY_MIN = _env_int("QUIZ_ANSWER_DELAY_MIN", 240)
# Ücretli X API oto cevap: tek çalışmada en fazla kaç yanıt
AUTO_REPLY_MAX = _env_int("AUTO_REPLY_MAX", 5)
FORCE = _env_flag("FORCE")  # FORCE=1 -> limit kontrolünü atla (test)
# Seri/quiz tweetlerinde en fazla kaç hashtag (eski usul tweetler 5 hashtag'le devam eder)
MAX_HASHTAGS = _env_int("MAX_HASHTAGS", 3)

TZ = ZoneInfo("Europe/Istanbul")
X_LIMIT = 280
STATE_PATH = os.getenv("STATE_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bot_state.json"
)

# --- HASHTAG GARANTİSİ VE ETKİLEŞİM HEDEFLERİ ---
DEFAULT_HASHTAGS = ["#Nature", "#Wildlife", "#Earth", "#NaturePhotography", "#Environment"]
TARGET_ACCOUNTS = ["NatGeo", "BBCEarth", "EarthPix", "ourplanet", "Discovery"]

# Bio için önerilen satır (X'teki "Otomasyon" etiketi elle açılır)
BIO_SUGGESTION = "Daily nature facts & quizzes 🌿 | 🤖 Automated account"


def ensure_hashtags(text: str) -> str:
    found_tags = re.findall(r"#\w+", text)
    if len(found_tags) < 5:
        missing = [tag for tag in DEFAULT_HASHTAGS if tag not in found_tags]
        text += " " + " ".join(missing[: 5 - len(found_tags)])
    return text.strip()


def limit_hashtags(text: str, extra=None, max_tags: int = None) -> str:
    """Seri/quiz tweetleri için: hashtag sayısını sınırlar, hiç yoksa extra'dan ekler."""
    max_tags = max_tags or MAX_HASHTAGS
    tags = re.findall(r"#\w+", text)
    body = re.sub(r"\s*#\w+", "", text).strip()
    keep = []
    for t in tags + list(extra or []):
        if t.lower() not in [k.lower() for k in keep]:
            keep.append(t)
    keep = keep[:max_tags]
    return (body + " " + " ".join(keep)).strip()


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


# ============================================================
#  DURUM DOSYASI (tekrar önleme, günlük limit, son konular)
# ============================================================
def load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st.setdefault("hashes", [])
    st.setdefault("posts", [])
    st.setdefault("replied_ids", [])
    st.setdefault("recent_texts", [])
    st.setdefault("since_id", None)
    return st


def save_state(st: dict):
    st["hashes"] = st["hashes"][-300:]
    st["posts"] = st["posts"][-100:]
    st["replied_ids"] = st["replied_ids"][-500:]
    st["recent_texts"] = st["recent_texts"][-10:]
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except OSError as e:
        print(f"Durum dosyası yazılamadı: {e}")


def text_hash(text: str) -> str:
    core = re.sub(r"#\w+", "", text.lower())
    core = re.sub(r"[^a-z0-9]+", " ", core).strip()
    return hashlib.sha1(core.encode("utf-8")).hexdigest()[:16]


def is_duplicate(st: dict, text: str) -> bool:
    return text_hash(text) in st["hashes"]


def posting_allowed(st: dict):
    """(izin, sebep). Limitler 0 ise (varsayılan) her zaman izin verir."""
    if FORCE or (DAILY_MAX_POSTS <= 0 and MIN_GAP_MIN <= 0):
        return True, "OK"
    now = datetime.now(TZ)
    times = []
    for s in st["posts"]:
        try:
            times.append(datetime.fromisoformat(s))
        except ValueError:
            pass
    if DAILY_MAX_POSTS > 0:
        today = [t for t in times if t.astimezone(TZ).date() == now.date()]
        if len(today) >= DAILY_MAX_POSTS:
            return False, f"Günlük limit doldu ({DAILY_MAX_POSTS})."
    if MIN_GAP_MIN > 0 and times:
        gap = (now - max(times)).total_seconds() / 60
        if gap < MIN_GAP_MIN:
            return False, f"Son paylaşımdan bu yana {int(gap)} dk geçti (min {MIN_GAP_MIN})."
    return True, "OK"


def record_post(st: dict, text: str):
    st["hashes"].append(text_hash(text))
    st["posts"].append(datetime.now(TZ).isoformat())
    save_state(st)


# --- YEDEK İÇERİK HAVUZU ---
FALLBACK_NOTES = [
    "Did you know? Trees in a forest can communicate and share nutrients through an underground fungal network. #NatureFacts #ForestLife #Trees #MotherNature #EcoSystem",
    "Bananas are naturally slightly radioactive because they contain high levels of potassium. #Science #Nature #ScienceFacts #Biology #NatureWonders",
    "Honey never spoils. Archeologists have found 3,000-year-old honey in ancient Egyptian tombs. #NatureMagic #Honey #History #AncientEgypt #FoodFacts",
    "A single full-grown oak tree can absorb up to 50 gallons of water per day. #Trees #Environment #Forests #SaveTrees #GreenPlanet",
    "Clouds look light and fluffy, but an average cumulus cloud weighs about 1.1 million pounds! #Weather #Nature #Atmosphere #Sky #NatureFacts",
]

# Kategori bilgili yedekler (görsel-metin uyumu için): (kategori, metin)
FALLBACK_BY_CAT = [
    ("trees", "Trees in a forest can share nutrients through an underground fungal network."),
    ("plants", "Bananas are naturally slightly radioactive because they contain potassium."),
    ("insects", "Honey never spoils. Archaeologists found 3,000-year-old honey in Egyptian tombs."),
    ("trees", "A single full-grown oak tree can absorb dozens of gallons of water per day."),
    ("weather", "An average cumulus cloud can weigh about a million pounds, yet it floats."),
    ("ocean", "An octopus has three hearts and blue blood."),
    ("animals", "Elephants can recognise themselves in a mirror, a sign of self-awareness."),
    ("birds", "Hummingbirds are the only birds that can fly backwards."),
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

# --- HAFTALIK KONU SERİSİ (0=Pazartesi ... 6=Pazar) ---
SERIES = {
    0: {"name": "Marine Monday", "cat": "ocean", "emoji": "🌊", "tag": "#MarineMonday"},
    1: {"name": "Tree Tuesday", "cat": "trees", "emoji": "🌳", "tag": "#TreeTuesday"},
    2: {"name": "Wild Wednesday", "cat": "animals", "emoji": "🐾", "tag": "#WildWednesday"},
    3: {"name": "Feathered Thursday", "cat": "birds", "emoji": "🐦", "tag": "#BirdThursday"},
    4: {"name": "Flora Friday", "cat": "plants", "emoji": "🌸", "tag": "#FloraFriday"},
    5: {"name": "Sky Saturday", "cat": "weather", "emoji": "⛅", "tag": "#SkySaturday"},
    6: {"name": "Small World Sunday", "cat": "insects", "emoji": "🐝", "tag": "#SmallWorldSunday"},
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
    pool = load_fact_pool()
    if not pool:
        return random.choice(FALLBACK_NOTES)
    now = datetime.now(TZ)
    idx = (now.toordinal() * 2 + (1 if now.hour >= 16 else 0)) % len(pool)
    cat, fact = pool[idx]
    tags = " ".join(CATEGORY_TAGS.get(cat, ["#Nature"]))
    return ensure_hashtags(f"{fact} {tags}")


def pick_pool_note_cat(want_cat=None, st=None):
    """(kategori, düz metin) döner. İstenen kategoriden, daha önce kullanılmamış bir bilgi seçer.
    LLM çökünce konu ile görselin uyuşmaması sorununu çözer."""
    pool = load_fact_pool()
    used = set(st["hashes"]) if st else set()
    if pool:
        cands = [p for p in pool if (not want_cat or p[0] == want_cat)] or pool
        random.shuffle(cands)
        for cat, fact in cands:
            if text_hash(fact) not in used:
                return cat, fact
        return cands[0]
    cands = [n for n in FALLBACK_BY_CAT if (not want_cat or n[0] == want_cat)] or FALLBACK_BY_CAT
    fresh = [n for n in cands if text_hash(n[1]) not in used]
    return random.choice(fresh or cands)


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


def call_llms(prompt: str, temperature: float = 0.7):
    generated = None
    if GEMINI_API_KEY:
        for attempt in range(1, 4):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                res = requests.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": temperature},
                    },
                    timeout=20,
                )
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
                "temperature": temperature,
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
                    "temperature": temperature,
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


def clean_llm_text(s: str) -> str:
    s = s.strip().strip('"').strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    return s


# ============================================================
#  ESKİ USUL: RASTGELE KONU (davranış aynı; sadece LLM çökünce konu-görsel uyumu düzeltildi)
# ============================================================
def generate_random_tweet(cat: str, st: dict):
    """(metin, kategori) döner."""
    ctx = get_season_context()
    topic, _ = TOPICS[cat]
    tags = " ".join(CATEGORY_TAGS.get(cat, ["#Nature"]))
    prompt = (
        f"Write an engaging English tweet containing ONE surprising, true and well-established fact about {topic}. "
        "Only state facts you are sure about and do not invent numbers. "
        f"Seasonal context (use only if it fits naturally): {ctx}. "
        "Max 230 characters in total including hashtags. "
        f"End with these hashtags plus 1-2 more relevant ones: {tags}. "
        "Output only the tweet text, no quotes, no preamble."
    )
    raw = call_llms(prompt)
    if raw:
        text = raw.strip().strip('"').strip()
    else:
        cat2, fact = pick_pool_note_cat(cat, st)
        cat = cat2 if cat2 in TOPICS else cat
        text = f"{fact} " + " ".join(CATEGORY_TAGS.get(cat, ["#Nature"]))
    return fit_for_x(ensure_hashtags(text)), cat


# ============================================================
#  1) KONU SERİSİ
# ============================================================
def generate_series_tweet(cat: str, series: dict, st: dict):
    """(metin, kategori) döner."""
    topic, _ = TOPICS[cat]
    tags = CATEGORY_TAGS.get(cat, ["#Nature"])
    recent = " | ".join(st.get("recent_texts", [])[-5:])
    prompt = (
        f"Write an engaging English tweet for the weekly series '{series['name']}'. "
        f"It must contain ONE surprising, true and well-established fact about {topic}. "
        "Only state facts you are sure about and do not invent numbers. "
        f"Start the tweet with the emoji {series['emoji']}. "
        "Max 220 characters including hashtags. "
        f"End with exactly these hashtags: {series['tag']} {tags[0]}. "
        + (f"Do NOT repeat any of these earlier topics: {recent}. " if recent else "")
        + "Output only the tweet text, no quotes, no preamble."
    )
    raw = call_llms(prompt)
    if raw:
        text = clean_llm_text(raw)
    else:
        cat2, fact = pick_pool_note_cat(cat, st)
        cat = cat2 if cat2 in TOPICS else cat
        text = f"{series['emoji']} {fact}"
    text = limit_hashtags(text, extra=[series["tag"], tags[0]])
    return fit_for_x(text), cat


# ============================================================
#  2) QUIZ (ücretsiz: soru + şıklar tweet'te, cevap birkaç saat sonra ayrı tweet)
# ============================================================
QUIZ_FALLBACK = [
    {"cat": "ocean", "q": "Which animal has three hearts?",
     "options": ["Octopus", "Dolphin", "Sea turtle"], "answer": 0,
     "explain": "An octopus has three hearts: two pump blood to the gills, one to the body."},
    {"cat": "animals", "q": "Which is the fastest land animal?",
     "options": ["Lion", "Cheetah", "Pronghorn"], "answer": 1,
     "explain": "The cheetah can sprint at roughly 100 km/h in short bursts."},
    {"cat": "trees", "q": "Which tree species is the tallest in the world?",
     "options": ["Giant sequoia", "Coast redwood", "Douglas fir"], "answer": 1,
     "explain": "Coast redwoods can exceed 110 metres, the tallest trees on Earth."},
    {"cat": "birds", "q": "Which bird can fly backwards?",
     "options": ["Hummingbird", "Eagle", "Swallow"], "answer": 0,
     "explain": "Hummingbirds can hover and even fly backwards thanks to their wing rotation."},
]

LETTERS = ["A", "B", "C"]


def generate_quiz(st: dict):
    cat = random.choice(list(TOPICS.keys()))
    topic, _ = TOPICS[cat]
    prompt = (
        f"Create ONE multiple-choice quiz question about {topic}. "
        "Only use facts you are 100% sure about. Exactly 3 short options, exactly one correct. "
        "Return ONLY valid JSON, no markdown, with this shape: "
        '{"q": "question under 90 characters", "options": ["a", "b", "c"], '
        '"answer": 0, "explain": "one short sentence under 110 characters"}. '
        "answer is the 0-based index of the correct option. Randomize the position of the correct option."
    )
    raw = call_llms(prompt, temperature=0.9)
    if raw:
        try:
            m = re.search(r"\{.*\}", clean_llm_text(raw), flags=re.S)
            data = json.loads(m.group(0))
            opts = [str(o).strip() for o in data["options"]][:3]
            ans = int(data["answer"])
            q = str(data["q"]).strip()
            explain = str(data["explain"]).strip()
            if len(opts) == 3 and 0 <= ans < 3 and q.endswith("?") and explain:
                return {"cat": cat, "q": q, "options": opts, "answer": ans, "explain": explain}
        except Exception as e:
            print(f"Quiz JSON ayrıştırılamadı: {e}")
    pool = [x for x in QUIZ_FALLBACK if text_hash(x["q"]) not in st["hashes"]] or QUIZ_FALLBACK
    return dict(random.choice(pool))


def format_quiz_tweet(quiz: dict) -> str:
    lines = [f"🧠 Nature Quiz: {quiz['q']}", ""]
    for i, opt in enumerate(quiz["options"]):
        lines.append(f"{LETTERS[i]}) {opt}")
    lines += ["", "Reply with your answer! Solution later today 👇"]
    tags = CATEGORY_TAGS.get(quiz["cat"], ["#Nature"])
    text = "\n".join(lines) + " #NatureQuiz " + tags[0]
    return fit_for_x(limit_hashtags(text))


def format_quiz_answer(quiz: dict) -> str:
    letter = LETTERS[quiz["answer"]]
    text = (
        f"✅ Quiz answer: {letter}) {quiz['options'][quiz['answer']]}\n\n"
        f"{quiz['explain']}\n\n"
        f"(Q: {quiz['q']})"
    )
    tags = CATEGORY_TAGS.get(quiz["cat"], ["#Nature"])
    return fit_for_x(limit_hashtags(text + " #NatureQuiz", extra=[tags[0]]))


# ============================================================
#  SORU (tweetin altına otomatik yorum)
# ============================================================
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


def fetch_media(query: str):
    """(url, is_video). Önce video aranır, bulunamazsa resme geçilir."""
    url = fetch_hd_video_url(query)
    if url:
        return url, True
    return fetch_hd_image_url(query), False


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


def create_buffer_post(channel_id: str, text: str, media_url=None, is_video=False,
                       reply=None, delay_min: int = 3) -> str:
    due = (datetime.now(timezone.utc) + timedelta(minutes=delay_min)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    assets = ""
    metadata = ""

    # Video ise GraphQL nesnesi 'video', resim ise 'image' olur
    media_asset_key = "video" if is_video else "image"

    if reply:
        first = "{ text: %s" % json.dumps(text, ensure_ascii=False)
        if media_url:
            first += f" assets: [{{ {media_asset_key}: {{ url: %s }} }}]" % json.dumps(media_url)
        first += " }"
        second = "{ text: %s }" % json.dumps(reply, ensure_ascii=False)
        metadata = "metadata: { twitter: { thread: [ %s %s ] } }" % (first, second)
    elif media_url:
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


def post_to_x(text: str, media_url=None, is_video=False, reply=None, delay_min: int = 3):
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
                post_id = create_buffer_post(channel_id, text, med, is_video=is_video and bool(med),
                                             reply=rp, delay_min=delay_min)
                print(f"✅ Buffer'a eklendi. Post ID: {post_id} | Video: {is_video and bool(med)} | yorum: {bool(rp)}")
                return True, "OK", bool(rp)
            except RuntimeError as e:
                print(f"Deneme başarısız: {e}")
                last_error = e
        raise last_error
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}", False


# ============================================================
#  3) CEVAP YARDIMCISI
#  ÜCRETSİZ yol : /cevap <gelen yorum> (Telegram) veya  python nature_bot.py --suggest "yorum"
#                 -> hazır cevap üretir, sen tek dokunuşla yapıştırırsın.
#  ÜCRETLİ yol  : X API anahtarları girilirse auto_reply_job() gelen yanıtlara kendisi cevap verir.
# ============================================================
def generate_reply(user_text: str, original_text: str) -> str:
    prompt = (
        "You run a friendly nature-facts account. Someone replied to our tweet.\n"
        f"Our tweet: {original_text[:200]}\n"
        f"Their reply: {user_text[:200]}\n\n"
        "Write ONE warm, specific reply (max 150 characters) that responds to what they actually said. "
        "If they answered a quiz, say whether it's right only if you are sure, otherwise just thank them. "
        "No hashtags, no quotation marks, no links. Output only the reply."
    )
    r = call_llms(prompt, temperature=0.9)
    if r:
        lines = clean_llm_text(r).splitlines()
        r = re.sub(r"#\w+", "", lines[0]).strip() if lines else ""
        if 5 <= len(r) <= 200:
            return fit_for_x(r)
    return random.choice([
        "Thanks for joining in! 🌿",
        "Great answer, thanks for sharing! 🌍",
        "Love hearing your take on this! 🍃",
        "Nature never stops surprising us, right? ✨",
    ])


def send_reply_suggestion(user_text: str, original_text: str = "a nature facts tweet") -> str:
    reply = generate_reply(user_text, original_text)
    safe = reply.replace("`", "'")
    notify_telegram(
        "↩️ *Önerilen cevap:*\n"
        f"`{safe}`\n\n"
        "🔗 [Gelen yanıtlar](https://x.com/notifications/mentions)"
    )
    return reply


def get_tweepy_client():
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        return None
    try:
        import tweepy  # pip install tweepy
    except ImportError:
        print("tweepy kurulu değil: pip install tweepy")
        return None
    return tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET,
        wait_on_rate_limit=False,
    )


def auto_reply_job() -> int:
    """ÜCRETLİ X API gerektirir; anahtar yoksa sessizce atlanır."""
    client = get_tweepy_client()
    if client is None:
        print("↩️ Otomatik cevap atlandı (X API anahtarı yok). Ücretsiz yol: /cevap veya --suggest.")
        return 0

    st = load_state()
    try:
        me = client.get_me()
        my_id = me.data.id
        resp = client.get_users_mentions(
            id=my_id,
            since_id=st.get("since_id"),
            max_results=20,
            expansions=["author_id", "referenced_tweets.id"],
            tweet_fields=["author_id", "conversation_id", "text"],
        )
    except Exception as e:
        print(f"Oto cevap: mention okunamadı: {e}")
        notify_telegram(f"⚠️ Oto cevap çalışmadı (X API): {str(e)[:200]}")
        return 0

    mentions = list(resp.data or [])
    if not mentions:
        return 0
    includes = {t.id: t for t in (resp.includes.get("tweets", []) if resp.includes else [])}

    st["since_id"] = str(max(int(t.id) for t in mentions))
    replied_authors = set()
    done = 0
    for t in sorted(mentions, key=lambda x: int(x.id)):
        if done >= AUTO_REPLY_MAX:
            break
        if str(t.id) in st["replied_ids"] or t.author_id == my_id:
            continue
        if t.author_id in replied_authors:
            continue
        original_text = ""
        for ref in (t.referenced_tweets or []):
            if ref.type == "replied_to" and ref.id in includes:
                original_text = includes[ref.id].text
        if not original_text:
            continue
        if re.search(r"https?://|follow back|f4f|dm me|giveaway", t.text, flags=re.I):
            continue
        reply = generate_reply(t.text, original_text)
        try:
            client.create_tweet(text=reply, in_reply_to_tweet_id=t.id)
            st["replied_ids"].append(str(t.id))
            replied_authors.add(t.author_id)
            done += 1
            print(f"↩️ Cevaplandı: {t.id} -> {reply}")
            time.sleep(random.randint(20, 60))
        except Exception as e:
            print(f"Cevap atılamadı {t.id}: {e}")
    save_state(st)
    if done:
        notify_telegram(f"↩️ {done} yanıta otomatik cevap verildi.")
    return done


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
        "• `/cevap <gelen yorum>` : Gelen yoruma hazır cevap önerir.\n"
        "• `/yardim` : Bu yardım rehberini gösterir.\n\n"
        "🗓️ *Haftalık seri:* Pzt Marine Monday, Sal Tree Tuesday, Çar Wild Wednesday, "
        "Per Feathered Thursday, Cum Flora Friday, Cmt Sky Saturday, Paz Small World Sunday.\n"
        "🧠 *Quiz:* Sal/Per/Cmt akşamı; cevap birkaç saat sonra ayrı tweet olarak çıkar.\n\n"
        "🛡️ *Neden API Kredisi Harcanmaz?*\n"
        "Paylaşımlar Buffer API üzerinden yapıldığı için hesabın X API sınırlarına takılmaz ve tamamen ücretsizdir.\n\n"
        "🤖 *Hesabı otomatik olarak etiketle:* X > Ayarlar > Hesabın > Hesap bilgileri > Otomasyon.\n"
        f"Bio önerisi: `{BIO_SUGGESTION}`"
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
        "3️⃣ *Sana gelen yanıtlar:*\n🔗 [Bildirimler](https://x.com/notifications/mentions)\n"
        "_(Yanıt varsa `/cevap yorum metni` yaz, hazır cevap göndereyim)_\n\n"
        "⏱️ _Süre: ~30 saniye. Beğeni ve takip elle yapıldığı için otomasyon kaynaklı hesap riski yok._"
    )
    notify_telegram(reminder_msg)


def check_telegram_updates():
    """OPSİYONEL (ENABLE_TELEGRAM_POLL=1): script çalışırken bekleyen /etkilesim, /yardim ve /cevap komutlarını işler."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            updates = res.json().get("result", [])
            for update in updates:
                msg = update.get("message", {})
                raw = msg.get("text", "").strip()
                text = raw.lower()
                if text in ["/etkilesim", "/etkileşim"]:
                    send_interaction_reminder()
                elif text in ["/yardim", "/yardım"]:
                    send_telegram_help()
                elif text.startswith("/cevap"):
                    body = raw[len("/cevap"):].strip()
                    if body:
                        send_reply_suggestion(body)
            if updates:
                # İşlenen güncellemeleri onayla, bir sonraki çalışmada tekrar gelmesin
                last_id = updates[-1]["update_id"]
                requests.get(url, params={"offset": last_id + 1}, timeout=5)
    except Exception as e:
        print(f"Telegram komut okuma hatası: {e}")


# ============================================================
#  ANA İŞ
# ============================================================
def choose_mode(now: datetime) -> str:
    if POST_MODE in ("series", "quiz", "random"):
        return POST_MODE
    if now.hour >= 16:
        # Salı, Perşembe, Cumartesi akşamı quiz; diğer akşamlar eski usul rastgele konu
        return "quiz" if now.weekday() in (1, 3, 5) else "random"
    return "series"


def build_content(mode: str, st: dict, now: datetime) -> dict:
    """Bir paylaşımın metnini hazırlar. Medya, metin kabul edildikten sonra çekilir."""
    c = {"answer_post": None, "reply_q": None, "cat": None}
    if mode == "weather":
        c["text"] = get_weather_info()
        c["query"] = "morning sunrise nature"
        c["title"] = "☀️ Sabah Hava Durumu Buffer'a eklendi"
        c["err_title"] = "❌ Hava Durumu Hata:"
    elif mode == "quiz":
        quiz = generate_quiz(st)
        c["text"] = format_quiz_tweet(quiz)
        c["answer_post"] = format_quiz_answer(quiz)
        c["cat"] = quiz["cat"]
        c["query"] = TOPICS.get(quiz["cat"], TOPICS["animals"])[1]
        c["title"] = f"🧠 Quiz ({quiz['cat']}) Buffer'a eklendi"
        c["err_title"] = "❌ Quiz Hatası:"
    elif mode == "series":
        series = SERIES[now.weekday()]
        text, cat = generate_series_tweet(series["cat"], series, st)
        c["text"], c["cat"] = text, cat
        c["query"] = TOPICS[cat][1]
        c["reply_q"] = generate_question(text)
        c["title"] = f"{series['name']} ({cat}) Buffer'a eklendi"
        c["err_title"] = "❌ Paylaşım Hatası:"
    else:  # random = eski davranış
        cat0 = random.choice(TOPIC_POOL)
        text, cat = generate_random_tweet(cat0, st)
        c["text"], c["cat"] = text, cat
        c["query"] = TOPICS[cat][1]
        c["reply_q"] = generate_question(text)
        c["title"] = f"İçerik ({cat}) Buffer'a eklendi"
        c["err_title"] = "❌ Paylaşım Hatası:"
    return c


def run_job(wait: bool = True, background_reminder: bool = False) -> bool:
    st = load_state()
    ok, why = posting_allowed(st)
    if not ok:
        print(f"⏸️ Paylaşım atlandı: {why}")
        return True  # hata değil, bilinçli atlama

    now = datetime.now(TZ)
    hour = now.hour
    if NATURE_MORNING_WEATHER and 7 <= hour < 10:
        mode = "weather"
    else:
        mode = choose_mode(now)

    # Aynı içerik daha önce atıldıysa en fazla 3 kez yeniden üret
    content = None
    for _ in range(3):
        cand = build_content(mode, st, now)
        if not is_duplicate(st, cand["text"]):
            content = cand
            break
        print("🔁 Aynı içerik daha önce paylaşılmış, yenisi üretiliyor...")
    if content is None:
        print("⏸️ Üç denemede de tekrar eden içerik çıktı, bu tur atlandı.")
        notify_telegram("⏸️ Tekrar eden içerik tespit edildi, bu tur paylaşım yapılmadı.")
        return True

    text = content["text"]
    question = content["reply_q"]
    answer_post = content["answer_post"]
    err_title = content["err_title"]

    # Medya, METNİN gerçek konusuna göre çekilir (görsel-metin uyumsuzluğunu önler)
    media_url, is_video = fetch_media(content["query"])
    media_type = "🎥 Video" if is_video else "📸 Görsel"
    title = f"{media_type} {content['title']}"

    success, reason, replied = post_to_x(text, media_url, is_video=is_video, reply=question)

    if success:
        st.setdefault("recent_texts", []).append(text[:60])
        record_post(st, text)

        msg = f"{title}\n\n{text}"
        if question:
            msg += f"\n\n💬 Yorum: {question}"
            if not replied:
                msg += "\n\n⚠️ Yorum eklenemedi, sadece ana tweet gitti (loga bak)."

        # Quiz cevabı: birkaç saat sonra ayrı tweet olarak zamanlanır
        if answer_post:
            ok2, reason2, _ = post_to_x(answer_post, None, delay_min=QUIZ_ANSWER_DELAY_MIN)
            if ok2:
                msg += f"\n\n✅ Cevap tweeti {QUIZ_ANSWER_DELAY_MIN // 60} saat sonraya zamanlandı:\n{answer_post}"
            else:
                msg += f"\n\n⚠️ Cevap tweeti zamanlanamadı: {reason2}"
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

    if "--suggest" in sys.argv:
        # Ücretsiz cevap yardımcısı: python nature_bot.py --suggest "gelen yorum metni"
        body = " ".join(sys.argv[sys.argv.index("--suggest") + 1:]).strip()
        if body:
            print(send_reply_suggestion(body))
        sys.exit(0)

    if "--reply" in sys.argv:
        # Sadece ÜCRETLİ X API oto cevap modu
        auto_reply_job()
        sys.exit(0)

    ok = run_job()
    try:
        auto_reply_job()  # X API anahtarı yoksa sessizce atlanır
    except Exception as e:
        print(f"Oto cevap hatası: {e}")
    sys.exit(0 if ok else 1)
