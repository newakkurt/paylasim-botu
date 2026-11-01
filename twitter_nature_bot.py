import csv
import difflib
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import urllib.parse
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


def _env_on(name: str, default: bool = True) -> bool:
    """Varsayılan AÇIK bayrak: sadece 0/false/no yazılırsa kapanır."""
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    return val.strip().lower() not in ("0", "false", "no")


# --- ENV VARIABLES ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "").strip()
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

# POST_MODE: auto | series | random | quiz | myth | thread
#   auto   = 16:00 öncesi günün serisi; 16:00 sonrası Salı/Perşembe/Cumartesi quiz, Çarşamba myth-vs-fact,
#            Pazar mini thread, Pazartesi/Cuma tek bilgi (random)
#   random = tek bilgi tweeti (rastgele konu)
POST_MODE = (os.getenv("POST_MODE") or "auto").strip().lower()
# Tekrar kontrolü HER ZAMAN açık. Aşağıdaki iki limit varsayılan KAPALI (0), istersen aç.
DAILY_MAX_POSTS = _env_int("DAILY_MAX_POSTS", 0)  # günlük en fazla paylaşım (0 = sınırsız)
MIN_GAP_MIN = _env_int("MIN_GAP_MIN", 0)          # iki paylaşım arası en az dakika (0 = kapalı)
# Quiz cevabı kaç dakika sonra ayrı tweet olarak yayınlansın
QUIZ_ANSWER_DELAY_MIN = _env_int("QUIZ_ANSWER_DELAY_MIN", 240)
# Ücretli X API oto cevap: tek çalışmada en fazla kaç yanıt
AUTO_REPLY_MAX = _env_int("AUTO_REPLY_MAX", 5)
FORCE = _env_flag("FORCE")  # FORCE=1 -> limit kontrolünü atla (test)
# Tweetlerde en fazla kaç hashtag (X'te 1-2 hashtag en iyi sonucu verir; eski varsayılan 3-5'ti)
MAX_HASHTAGS = _env_int("MAX_HASHTAGS", 2)

# --- İDDİA KONTROLÜ VE BENZERLİK ---
# FACT_CHECK=0 -> kapatır. Varsayılan AÇIK: tweet paylaşılmadan önce ikinci bir model sayı/olgu iddialarını denetler.
FACT_CHECK = (os.getenv("FACT_CHECK") or "1").strip().lower() not in ("0", "false", "no")
# FACT_CHECK_STRICT=1 -> doğrulayıcı model hiç cevap veremezse paylaşım yapılmaz.
# Varsayılan (0): doğrulanamazsa yine paylaşır ama Telegram'da uyarı düşer, bot kota hatasında durmaz.
FACT_CHECK_STRICT = _env_flag("FACT_CHECK_STRICT")
# Yeni tweet geçmiştekilerden bu yüzde veya daha fazla benziyorsa yeniden üretilir (0 = kapalı)
SIMILARITY_PCT = _env_int("SIMILARITY_PCT", 60)
# Şüpheli/tekrar/benzer çıkarsa en fazla kaç kez yeniden üretilsin
MAX_ATTEMPTS = _env_int("MAX_ATTEMPTS", 4)

# --- v2: KAYNAKLI ÜRETİM, HOOK PUANI, ÇEŞİTLİLİK ---
# USE_SOURCES=0 -> Wikipedia kaynağı kapatılır, model kendi bilgisiyle yazar (eski davranış)
USE_SOURCES = _env_on("USE_SOURCES", True)
# SOURCE_IN_REPLY=0 -> kaynak linki alt yorumda gösterilmez
SOURCE_IN_REPLY = _env_on("SOURCE_IN_REPLY", True)
# İkinci model hook'a bu puanın altında not verirse taslak yeniden yazılır (1-10)
HOOK_MIN = _env_int("HOOK_MIN", 6)
# Buffer gecikmesine 0..N dakika rastgele eklenir (her tweet tam aynı dakikada çıkmasın)
POST_JITTER_MAX = _env_int("POST_JITTER_MAX", 5)

TZ = ZoneInfo("Europe/Istanbul")
X_LIMIT = 280
STATE_PATH = os.getenv("STATE_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bot_state.json"
)

# --- HASHTAG GARANTİSİ VE ETKİLEŞİM HEDEFLERİ ---
DEFAULT_HASHTAGS = ["#Nature", "#Wildlife", "#Earth", "#NaturePhotography", "#Environment"]
TARGET_ACCOUNTS = [a.strip().lstrip("@") for a in (os.getenv("TARGET_ACCOUNTS") or "NatGeo,BBCEarth,EarthPix,ourplanet,Discovery").split(",") if a.strip()]

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
    st.setdefault("history", [])  # paylaşılan tweetlerin tam metni (benzerlik kontrolü için)
    st.setdefault("since_id", None)
    st.setdefault("used_sources", [])  # kullanılan Wikipedia makaleleri (tekrar seçilmez)
    st.setdefault("media_used", [])    # kullanılan Pexels/Unsplash görsel-video id'leri
    return st


def save_state(st: dict):
    st["hashes"] = st["hashes"][-300:]
    st["history"] = st["history"][-200:]
    st["posts"] = st["posts"][-100:]
    st["replied_ids"] = st["replied_ids"][-500:]
    st["recent_texts"] = st["recent_texts"][-10:]
    st["used_sources"] = st["used_sources"][-400:]
    st["media_used"] = st["media_used"][-200:]
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


def record_post(st: dict, text: str, meta: dict = None):
    """meta: cat, mode, hook_style, hook, source gibi alanlar; performans analizi için geçmişle birlikte saklanır."""
    st["hashes"].append(text_hash(text))
    now = datetime.now(TZ).isoformat()
    st["posts"].append(now)
    entry = {"text": text, "t": now}
    entry.update({k: v for k, v in (meta or {}).items() if v is not None})
    st.setdefault("history", []).append(entry)
    save_state(st)


# ============================================================
#  BENZERLİK KONTROLÜ (aynı konu/cümleyi başka kelimelerle tekrar atmayı engeller)
# ============================================================
_BOILER = re.compile(
    r"nature quiz|reply with your answer|solution later today|quiz answer|\b[abc]\)", re.I
)
_STOP = {
    "that", "this", "with", "from", "have", "which", "their", "than", "they", "when",
    "into", "about", "more", "most", "after", "also", "only", "even", "over", "such",
    "some", "each", "other", "while", "there", "these", "those", "years", "year",
}


def _core_text(text: str) -> str:
    t = _BOILER.sub(" ", text.lower())
    t = re.sub(r"#\w+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similarity(a: str, b: str) -> float:
    """0..1 arası benzerlik: karakter dizisi oranı ile anlamlı kelime kesişiminin büyüğü."""
    ca, cb = _core_text(a), _core_text(b)
    if not ca or not cb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, ca, cb).ratio()
    wa = {w for w in ca.split() if len(w) > 3 and w not in _STOP}
    wb = {w for w in cb.split() if len(w) > 3 and w not in _STOP}
    jac = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    return max(ratio, jac)


def find_similar(st: dict, text: str):
    """Eşik aşılırsa (oran, eşleşen_eski_metin) döner, aşılmazsa None."""
    if SIMILARITY_PCT <= 0:
        return None
    best, best_txt = 0.0, None
    for h in st.get("history", [])[-150:]:
        old = h.get("text", "") if isinstance(h, dict) else str(h)
        s = similarity(text, old)
        if s > best:
            best, best_txt = s, old
    if best >= SIMILARITY_PCT / 100:
        return best, best_txt
    return None


def avoid_clause(st: dict, n: int = 8) -> str:
    """Prompt'a eklenir: model son paylaşımları baştan tekrar etmesin."""
    items = []
    for h in st.get("history", [])[-n:]:
        old = h.get("text", "") if isinstance(h, dict) else str(h)
        core = _core_text(old)[:70]
        if core:
            items.append(core)
    if not items:
        return ""
    return "Do NOT repeat or paraphrase any of these recent posts: " + " | ".join(items) + ". "


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


# ============================================================
#  LLM ROUTER (Shorts botundaki zincirle aynı mantık, 3 farkla)
#   1) Kota/404 yiyen model KALICI ölmez, süreli soğumaya girer (Render'daki 7/24 süreç için şart).
#   2) "Hızlı model" ayrımı model adındaki 8b / 20b / mini parçalarına bakar; "gemini" ve "gpt-oss-120b"
#      yanlışlıkla hızlı sayılmaz.
#   3) Doğrulayıcı, üreticiyle AYNI sağlayıcı ailesinden çalışmamaya çalışır (kendi uydurmasını onaylamasın).
# ============================================================
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_MODELS = [
    m.strip()
    for m in (os.getenv("GROQ_MODELS") or "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",")
    if m.strip()
]
_FAST_RE = re.compile(r"(?<![\w.])(?:8|20)b(?!\w)|(?:^|[-/])mini(?:$|[-:])", re.I)
_cooldown = {}       # model adı -> tekrar denenebileceği zaman (epoch)
_last_family = None  # son başarılı çağrının sağlayıcı ailesi: gemini | groq | openrouter


def _is_fast(name: str) -> bool:
    return bool(_FAST_RE.search(name.split(":", 1)[-1]))


def _gemini_call(prompt: str, temperature: float, as_json: bool) -> str:
    cfg = {"temperature": temperature}
    if as_json:
        cfg["responseMimeType"] = "application/json"
    res = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg},
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"{res.status_code} {res.text[:150]}")
    parts = res.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _chat_call(url: str, key: str, model: str, prompt: str, temperature: float, timeout: int = 30) -> str:
    res = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature},
        timeout=timeout,
    )
    if res.status_code != 200:
        raise RuntimeError(f"{res.status_code} {res.text[:150]}")
    return res.json()["choices"][0]["message"]["content"]


def _chain(as_json: bool, tier: str = "strong", avoid_family=None):
    chain = []
    if GEMINI_API_KEY:
        chain.append((f"gemini:{GEMINI_MODEL}", lambda p, t: _gemini_call(p, t, as_json)))
    if GROQ_API_KEY:
        for m in GROQ_MODELS:
            chain.append((f"groq:{m}", lambda p, t, m=m: _chat_call(GROQ_URL, GROQ_API_KEY, m, p, t)))
    # OpenRouter is opt-in: old free model slugs were returning 404.
    if OPENROUTER_API_KEY and OPENROUTER_MODEL:
        chain.append((
            f"openrouter:{OPENROUTER_MODEL}",
            lambda p, t: _chat_call(OPENROUTER_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL, p, t, 40),
        ))
    now = time.time()
    chain = [c for c in chain if _cooldown.get(c[0], 0) <= now]
    # sort kararlıdır: aynı gruptakiler kendi sırasını korur
    if tier == "fast":
        chain.sort(key=lambda c: 0 if _is_fast(c[0]) else 1)
    else:
        chain.sort(key=lambda c: 1 if _is_fast(c[0]) else 0)
    if avoid_family:
        chain.sort(key=lambda c: c[0].split(":", 1)[0] == avoid_family)
    return chain


def _clean(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _extract_json(text: str):
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def _ask(prompt: str, as_json: bool = True, tier: str = "strong", temperature: float = 0.7, avoid_family=None):
    """Zincirdeki modelleri sırayla dener. Başarılıysa metin, hepsi başarısızsa None döner."""
    global _last_family
    chain = _chain(as_json, tier, avoid_family)
    if not chain:
        print("LLM: kullanılabilir model yok (anahtar eksik ya da hepsi soğumada).")
        return None
    for rnd in range(2):
        for name, fn in list(chain):
            try:
                text = _clean(fn(prompt, temperature) or "")
                if as_json:
                    text = json.dumps(_extract_json(text), ensure_ascii=False)
                if text:
                    _last_family = name.split(":", 1)[0]
                    return text
            except Exception as e:
                msg = str(e)
                print(f"LLM hata {name}: {msg[:120]}")
                code = msg[:3] if msg[:3].isdigit() else ""
                if code == "429":
                    _cooldown[name] = time.time() + 1800    # kota: yarım saat dinlendir
                elif code in ("401", "403", "404"):
                    _cooldown[name] = time.time() + 86400   # yanlış model adı / anahtar: bir gün
                if _cooldown.get(name, 0) > time.time():
                    chain = [c for c in chain if c[0] != name]
        if not chain:
            break
        time.sleep(3 * (rnd + 1))
    return None


def call_llms(prompt: str, temperature: float = 0.7):
    """Eski imza korunur: metin döner, hepsi başarısız olursa None."""
    return _ask(prompt, as_json=False, tier="strong", temperature=temperature)


def call_llms_json(prompt: str, temperature: float = 0.7, tier: str = "strong", avoid_family=None):
    """JSON üretir; dict döner, olmazsa None."""
    raw = _ask(prompt, as_json=True, tier=tier, temperature=temperature, avoid_family=avoid_family)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def generate_ai_text(prompt: str) -> str:
    generated = call_llms(prompt) or pick_pool_note()
    generated = generated.strip().strip('"').strip()
    return fit_for_x(ensure_hashtags(generated))


def clean_llm_text(s: str) -> str:
    s = s.strip().strip('"').strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    return s


# ============================================================
#  İDDİA KONTROLÜ + HOOK PUANI (tek çağrı, ikinci model, sıcaklık 0)
#  Kaynak (Wikipedia özeti) varsa soru "kaynakta yazıyor mu?" olur; modelin kendi hafızasına güvenilmez.
#  Doğrulayıcı mümkünse üreticiden FARKLI sağlayıcı ailesinden seçilir.
# ============================================================
def call_verifier(prompt: str):
    return _ask(prompt, as_json=False, tier="strong", temperature=0.0, avoid_family=_last_family)


def review_draft(check_text: str, src=None, avoid_family=None):
    """(verdict, hook, issues). verdict: 'ok' | 'suspicious' | 'unverified'. hook: 1-10 ya da None."""
    if src:
        basis = (
            "The ONLY fact base is the SOURCE below (Wikipedia). Answer 'suspicious' if the text contains ANY number, "
            "name, date or claim that is not stated in SOURCE or that distorts it. Only truly universal common "
            "knowledge may go beyond SOURCE.\n"
            f"SOURCE ({src['title']}): {src['extract']}\n\n"
        )
    else:
        basis = (
            "No source is given. Answer 'suspicious' if ANY claim is wrong, exaggerated, outdated, disputed, or if a "
            "number cannot be confirmed from well-established knowledge.\n\n"
        )
    prompt = (
        "You are a strict fact-checker and social media editor for a nature-facts account on X. "
        + basis
        + "Answer 'ok' only if every claim is correct. "
        "If the text is a quiz, also verify that the marked answer is the single correct option. "
        "Also rate the HOOK (the first line) from 1 to 10: 10 = specific, surprising, scroll-stopping; "
        "5 = generic ('Did you know...'); 1 = boring. Do not judge anything else about style.\n\n"
        f"TEXT:\n{check_text}\n\n"
        'Return ONLY valid JSON, no markdown: {"verdict": "ok" or "suspicious", "hook": 1-10, "issues": ["short concrete fix"]}.'
    )
    raw = _ask(prompt, as_json=True, tier="strong", temperature=0.0, avoid_family=avoid_family)
    if not raw:
        return "unverified", None, ["Doğrulayıcı model cevap vermedi."]
    try:
        data = json.loads(raw)
        verdict = str(data.get("verdict", "")).strip().lower()
        issues = [str(i)[:160] for i in (data.get("issues") or [])][:4]
        try:
            hook = max(1, min(10, int(float(data.get("hook")))))
        except (TypeError, ValueError):
            hook = None
        if verdict == "ok":
            return "ok", hook, issues
        if verdict == "suspicious":
            return "suspicious", hook, issues or ["Şüpheli iddia (ayrıntı verilmedi)."]
    except Exception as e:
        print(f"Doğrulama cevabı ayrıştırılamadı: {e}")
    return "unverified", None, ["Doğrulama cevabı okunamadı."]


def fact_check(text: str, source=None):
    """Eski imza: (durum, notlar). durum: 'ok' | 'suspicious' | 'unverified'."""
    verdict, _hook, issues = review_draft(text, source)
    return verdict, issues


# ============================================================
#  KAYNAKLI ÜRETİM (v2)
#  Shorts botundaki "grounding" mantığının doğa karşılığı: konu için Wikipedia'dan gerçek bir özet çekilir,
#  model SADECE o metindeki bilgiyle yazar, doğrulayıcı da aynı metne karşı kontrol eder.
#  Kaynak bulunamazsa eski davranışa düşer (modelin kendi bilgisi + doğrulayıcı).
# ============================================================
WIKI_API = "https://en.wikipedia.org/w/api.php"
HTTP_HEADERS = {"User-Agent": "NatureFactsBot/2.0 (automated nature facts account; GitHub Actions)"}

# Kategori başına Wikipedia arama tohumları. Her seferinde biri seçilir, sonuçlardan kullanılmamış bir makale alınır.
SOURCE_SEEDS = {
    "animals": ["apex predator", "primate behaviour", "big cat", "elephant", "marsupial", "nocturnal mammal",
                "animal migration", "endangered species"],
    "birds": ["migratory bird", "bird of prey", "songbird", "flightless bird", "seabird", "owl", "hummingbird",
              "corvid intelligence"],
    "trees": ["old-growth forest", "tree species", "rainforest canopy", "bristlecone pine", "mangrove", "redwood",
              "forest ecology", "tree rings"],
    "ocean": ["deep sea creature", "coral reef", "whale", "shark", "octopus", "jellyfish", "kelp forest",
              "bioluminescence"],
    "water": ["waterfall", "river delta", "freshwater lake", "glacial lake", "wetland", "hot spring", "estuary",
              "aquifer"],
    "plants": ["carnivorous plant", "wildflower", "orchid", "desert plant", "pollination", "seed dispersal", "moss",
               "alpine plant"],
    "insects": ["pollinator bee", "butterfly migration", "ant colony", "dragonfly", "beetle", "social insect",
                "firefly", "cicada"],
    "earth": ["volcano", "canyon", "mountain range", "cave system", "desert landscape", "geyser", "island formation",
              "rock formation"],
    "weather": ["cloud type", "thunderstorm", "aurora", "rainbow", "fog", "monsoon", "lightning", "snow crystal"],
    "fungi": ["mushroom species", "mycorrhiza", "bioluminescent fungus", "lichen", "mold ecology", "puffball",
              "truffle", "slime mold"],
}

# Hook (ilk satır) kalıpları. Metrik verisi varsa en iyi giden kalıp daha sık seçilir (epsilon-greedy), yoksa dönüşümlü.
HOOK_STYLES = {
    "number": "open with a specific, surprising number or measurement",
    "question": "open with a short curiosity question that the rest of the tweet answers",
    "contrast": "open with a reversal: it looks like X, but actually Y",
    "scene": "open with a vivid one-line scene that puts the reader in the moment",
    "superlative": "open with a superlative (the only, the largest, the oldest, the fastest) that is actually true",
}


# ---------- performans geri beslemesi (Shorts'taki winners() karşılığı) ----------
def _scored(st: dict):
    return [h for h in st.get("history", [])
            if isinstance(h, dict) and isinstance(h.get("score"), (int, float))]


def winners(st: dict, n: int = 4):
    """Skoru en yüksek n paylaşımın temiz metni (prompt'a stil örneği olarak girer). Skor yoksa boş liste."""
    rows = sorted((h for h in _scored(st) if h.get("text") and h["score"] > 0), key=lambda h: h["score"], reverse=True)
    return [re.sub(r"\s*#\w+", "", h["text"]).strip() for h in rows[:n]]


def choose_hook_style(st: dict) -> str:
    """Yeterli skor varsa %70 en iyi ortalamalı kalıp, aksi halde son 3'te kullanılmayanlardan rastgele."""
    scored = [h for h in _scored(st) if h.get("hook_style") in HOOK_STYLES]
    if len(scored) >= 12 and random.random() > 0.3:
        avg = {}
        for s in HOOK_STYLES:
            vals = [h["score"] for h in scored if h["hook_style"] == s]
            if len(vals) >= 2:
                avg[s] = sum(vals) / len(vals)
        if avg:
            return max(avg, key=avg.get)
    recent = [h.get("hook_style") for h in st.get("history", [])[-3:] if isinstance(h, dict)]
    pool = [s for s in HOOK_STYLES if s not in recent] or list(HOOK_STYLES)
    return random.choice(pool)


def pick_category(st: dict) -> str:
    """Son 2 paylaşımın kategorisini tekrarlamaz; yeterli skor varsa %70 en iyi ortalamalı kategoriyi seçer."""
    recent = [h.get("cat") for h in st.get("history", [])[-2:] if isinstance(h, dict)]
    pool = [c for c in TOPIC_POOL if c not in recent] or list(TOPIC_POOL)
    scored = [h for h in _scored(st) if h.get("cat") in TOPICS]
    if len(scored) >= 12 and random.random() > 0.3:
        avg = {}
        for c in set(pool):
            vals = [h["score"] for h in scored if h["cat"] == c]
            if len(vals) >= 2:
                avg[c] = sum(vals) / len(vals)
        if avg:
            return max(avg, key=avg.get)
    return random.choice(pool)


def plan_category(mode: str, st: dict, now: datetime):
    if mode == "weather":
        return None
    if mode == "series":
        return SERIES[now.weekday()]["cat"]
    return pick_category(st)


_URL_RE = re.compile(r"(?:https?://|pic\.(?:twitter|x)\.com/)\S+", re.I)


def _core_key(text: str) -> str:
    return _core_text(_URL_RE.sub(" ", text or ""))[:40]


def _num(row: dict, *names):
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            try:
                return float(str(v).replace(",", "").replace(" ", ""))
            except ValueError:
                pass
    return 0.0


def import_metrics(path: str) -> int:
    """X Analytics'ten (ya da elle hazırlanmış) CSV'deki beğeni/yanıt/repost sayılarını geçmişle eşleştirip skor yazar.
    Kullanım: python nature_bot.py --import-metrics export.csv  (sonra bot_state.json'u repoya commit et)."""
    st = load_state()
    index = {_core_key(h["text"]): h for h in st["history"] if isinstance(h, dict) and h.get("text")}
    matched = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            low = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            text = low.get("post text") or low.get("tweet text") or low.get("text") or ""
            h = index.get(_core_key(text))
            if h is None:
                continue
            likes = _num(low, "likes", "like count")
            replies = _num(low, "replies", "reply count")
            reposts = _num(low, "reposts", "retweets", "retweet count")
            bookmarks = _num(low, "bookmarks", "bookmark count")
            imps = _num(low, "impressions", "views")
            score = likes + 3 * replies + 2 * reposts + 2 * bookmarks
            if not score and imps:
                score = imps / 50
            h["score"] = round(score, 1)
            if imps:
                h["impressions"] = int(imps)
            matched += 1
    save_state(st)
    return matched


# ---------- kaynak seçimi ----------
def _wiki_extract(title: str):
    try:
        res = requests.get(
            WIKI_API,
            params={"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "redirects": 1,
                    "titles": title, "format": "json"},
            headers=HTTP_HEADERS, timeout=10,
        )
        res.raise_for_status()
        page = next(iter(res.json()["query"]["pages"].values()))
        text = re.sub(r"\s+", " ", page.get("extract") or "").strip()
        if len(text) < 300 or "may refer to" in text[:250]:
            return None
        real = page.get("title", title)
        return {
            "title": real,
            "extract": text[:1800],
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(real.replace(" ", "_")),
        }
    except Exception as e:
        print(f"Wikipedia özet hatası ({title}): {e}")
        return None


def pick_source(cat: str, st: dict):
    """Kategoriye uygun, daha önce kullanılmamış bir Wikipedia özeti. Bulunamazsa None (akış eski moda düşer)."""
    if not USE_SOURCES:
        return None
    seeds = SOURCE_SEEDS.get(cat) or SOURCE_SEEDS["animals"]
    used = set(st.get("used_sources", []))
    for _ in range(3):
        term = random.choice(seeds)
        try:
            res = requests.get(
                WIKI_API,
                params={"action": "query", "list": "search", "srsearch": term, "srnamespace": 0,
                        "srlimit": 20, "format": "json"},
                headers=HTTP_HEADERS, timeout=10,
            )
            res.raise_for_status()
            titles = [h["title"] for h in res.json()["query"]["search"]]
        except Exception as e:
            print(f"Wikipedia arama hatası: {e}")
            continue
        random.shuffle(titles)
        for title in titles[:8]:
            low = title.lower()
            if title in used or low.startswith(("list of", "outline of", "index of")) or "disambiguation" in low:
                continue
            src = _wiki_extract(title)
            if src:
                return src
    return None


# ---------- yazar ----------
def _source_block(src) -> str:
    if not src:
        return "No source is provided: only state facts you are 100% sure about and never invent numbers, names or dates. "
    return (
        "SOURCE (Wikipedia) is the ONLY allowed fact base. Every number, name, date and claim you write MUST be stated "
        "in it; paraphrase in your own words, never copy sentences, add nothing from memory:\n"
        f'"""{src["title"]}: {src["extract"]}"""\n'
    )


def _writer_prompt(kind, cat, st, src, series, hook_style, feedback) -> str:
    topic = TOPICS[cat][0]
    if kind == "series":
        task = (f"Write ONE tweet for the weekly series '{series['name']}' containing ONE surprising, true fact about "
                f"{topic}. Start the body with the emoji {series['emoji']}. Body max 190 characters. ")
    elif kind == "myth":
        task = (f"Write ONE 'myth vs fact' tweet about {topic}: first line a genuinely common misconception "
                "('Myth: ...'), then the truth ('Fact: ...'). Body max 230 characters. ")
    elif kind == "thread":
        task = (f"Write a 3-tweet mini thread about {topic}. tweets[0]: a scroll-stopping hook that promises a payoff, "
                "max 200 characters. tweets[1] and tweets[2]: one concrete fact each, max 240 characters each. "
                "No numbering like 1/3 and no hashtags inside the tweets. ")
    else:
        task = (f"Write ONE tweet containing ONE surprising, true fact about {topic}. Body max 200 characters. "
                f"Seasonal context (use only if it fits naturally): {get_season_context()}. ")
    hook = "" if kind == "myth" else f"Hook style for the first line: {HOOK_STYLES[hook_style]}. "
    win = winners(st)
    win_block = (
        "Our best-performing posts so far (learn the style and curiosity pattern, do NOT copy): "
        + " | ".join(win) + ". "
    ) if win else ""
    if kind == "thread":
        schema = '{"tweets": ["hook tweet", "fact tweet", "fact tweet"], '
    else:
        schema = '{"text": "tweet body WITHOUT hashtags", '
    schema += ('"hashtags": ["#SpecificTag", "#BroadTag"], '
               '"keyword": "2-3 English words for a stock photo or video of the subject, e.g. humpback whale", '
               '"question": "one short follow-up question that invites replies, max 120 characters"}')
    return (
        "You run a popular, trustworthy nature-facts account on X (Twitter). "
        + task + _source_block(src) + hook
        + "Write like a curious human: concrete, vivid, no filler. Never open with 'Did you know'. Use at most one emoji. "
        + win_block + avoid_clause(st) + (feedback + " " if feedback else "")
        + "\nReturn ONLY valid JSON, no markdown, with this shape: " + schema
    )


def _clean_body(s) -> str:
    s = clean_llm_text(str(s or ""))
    s = re.sub(r"\s*#\w+", "", s)
    return re.sub(r"[ \t]+\n", "\n", s).strip()


def _clean_question(q):
    if not q:
        return None
    lines = str(q).strip().strip('"').strip().splitlines()
    if not lines:
        return None
    q = re.sub(r"#\w+", "", lines[0]).strip().strip('"').strip()
    return q if "?" in q and 10 <= len(q) <= 200 else None


def _closing_reply(q: str, src) -> str:
    """Alt yorum: soru + (varsa) kaynak linki. Link ana tweette değil, yorumda durur (erişimi düşürmez)."""
    q = fit_for_x(q)
    if src and SOURCE_IN_REPLY:
        link = f"\n\n📚 Source: {src['url']}"
        if x_length(q) + len(link) <= 275:
            return q + link
    return q


def generate_post(kind, cat, st, src=None, series=None, hook_style=None, feedback=""):
    """kind: fact | series | myth | thread.
    Döner: text, followups, keyword, cat, hook_style, src, family, check_text, kind."""
    hook_style = hook_style or choose_hook_style(st)
    defaults = CATEGORY_TAGS.get(cat, ["#Nature"])
    data, family = None, None
    raw = _ask(_writer_prompt(kind, cat, st, src, series, hook_style, feedback),
               as_json=True, tier="strong", temperature=0.8)
    if raw:
        family = _last_family
        try:
            data = json.loads(raw)
        except ValueError:
            data = None

    follow, keyword, question, llm_tags = [], None, None, []
    try:
        if not isinstance(data, dict):
            raise ValueError("model cevap vermedi")
        if kind == "thread":
            tweets = [_clean_body(t) for t in (data.get("tweets") or [])][:3]
            if len(tweets) < 3 or any(len(t) < 25 for t in tweets):
                raise ValueError("thread eksik")
            body, follow = tweets[0], tweets[1:]
        else:
            body = _clean_body(data.get("text"))
            if len(body) < 30:
                raise ValueError("metin çok kısa")
        keyword = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z ]", " ", str(data.get("keyword") or ""))).strip()[:40] or None
        question = _clean_question(data.get("question"))
        for t in data.get("hashtags") or []:
            t = str(t).strip()
            t = t if t.startswith("#") else "#" + t
            if re.fullmatch(r"#\w{2,30}", t):
                llm_tags.append(t)
    except Exception as e:
        # Model çöktü/saçmaladı: havuzdan düz bilgi. Kaynağa dayanmadığı için src düşer.
        print(f"Yazar çıktısı kullanılamadı ({e}); havuz bilgisine düşülüyor.")
        cat2, fact = pick_pool_note_cat(cat, st)
        cat = cat2 if cat2 in TOPICS else cat
        defaults = CATEGORY_TAGS.get(cat, ["#Nature"])
        body = f"{series['emoji']} {fact}" if series else fact
        follow, keyword, question, llm_tags = [], None, None, []
        kind = "series" if series else "fact"
        src, family = None, None

    if series and not body.startswith(series["emoji"]):
        # model başka bir emoji/işaretle başladıysa onu at, seri emojisini başa koy (çift emoji olmasın)
        body = f"{series['emoji']} " + re.sub(r"^[^\w#@]+", "", body)
    extra = [series["tag"], defaults[0]] if series else llm_tags + defaults
    text = fit_for_x(limit_hashtags(body, extra=extra))

    followups = [fit_for_x(t) for t in follow]
    q = question or random.choice(QUESTION_BANK.get(cat) or QUESTION_BANK["generic"])
    followups.append(_closing_reply(q, src))

    check_text = text if not follow else text + "\n---\n" + "\n".join(follow)
    return {
        "text": text, "followups": followups, "keyword": keyword, "cat": cat, "hook_style": hook_style,
        "src": src, "family": family, "check_text": check_text, "kind": kind,
    }


def generate_random_tweet(cat: str, st: dict):
    """Eski imza: (metin, kategori)."""
    post = generate_post("fact", cat, st, src=pick_source(cat, st))
    return post["text"], post["cat"]


def generate_series_tweet(cat: str, series: dict, st: dict):
    """Eski imza: (metin, kategori)."""
    post = generate_post("series", cat, st, src=pick_source(cat, st), series=series)
    return post["text"], post["cat"]


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


def generate_quiz(st: dict, src=None, cat=None):
    cat = cat if cat in TOPICS else pick_category(st)
    topic, _ = TOPICS[cat]
    prompt = (
        f"Create ONE multiple-choice quiz question about {topic}. "
        + _source_block(src)
        + "Exactly 3 short options, exactly one correct; the correct answer must be a fact you are 100% sure about"
        + (" and it must be stated in the SOURCE. " if src else ". ")
        + "Return ONLY valid JSON, no markdown, with this shape: "
        '{"q": "question under 90 characters", "options": ["a", "b", "c"], '
        '"answer": 0, "explain": "one short sentence under 110 characters", '
        '"keyword": "2-3 English words for a stock photo of the subject"}. '
        "answer is the 0-based index of the correct option. Randomize the position of the correct option. "
        + avoid_clause(st)
    )
    data = call_llms_json(prompt, temperature=0.9)
    if data:
        try:
            opts = [str(o).strip() for o in data["options"]][:3]
            ans = int(data["answer"])
            q = str(data["q"]).strip()
            explain = str(data["explain"]).strip()
            if len(opts) == 3 and 0 <= ans < 3 and q.endswith("?") and explain:
                kw = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z ]", " ", str(data.get("keyword") or ""))).strip()[:40] or None
                return {"cat": cat, "q": q, "options": opts, "answer": ans, "explain": explain,
                        "keyword": kw, "used_src": bool(src)}
        except Exception as e:
            print(f"Quiz JSON ayrıştırılamadı: {e}")
    pool = [x for x in QUIZ_FALLBACK if text_hash(x["q"]) not in st["hashes"]] or QUIZ_FALLBACK
    quiz = dict(random.choice(pool))
    quiz["used_src"] = False
    return quiz


def format_quiz_tweet(quiz: dict) -> str:
    lines = [f"🧠 Nature Quiz: {quiz['q']}", ""]
    for i, opt in enumerate(quiz["options"]):
        lines.append(f"{LETTERS[i]}) {opt}")
    lines += ["", "Reply with your answer! Solution later today 👇"]
    tags = CATEGORY_TAGS.get(quiz["cat"], ["#Nature"])
    text = "\n".join(lines) + " #NatureQuiz " + tags[0]
    return fit_for_x(limit_hashtags(text))


def format_quiz_answer(quiz: dict, src_url: str = None) -> str:
    letter = LETTERS[quiz["answer"]]
    text = (
        f"✅ Quiz answer: {letter}) {quiz['options'][quiz['answer']]}\n\n"
        f"{quiz['explain']}\n\n"
        f"(Q: {quiz['q']})"
    )
    if src_url and SOURCE_IN_REPLY and len(text) + len(src_url) + 12 <= 265:
        text += f"\n\n📚 {src_url}"
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

def _pexels_video(query: str, used: set):
    """(id, url). 45 sn'den uzun klipleri ve daha önce kullanılanları eler."""
    if not PEXELS_API_KEY:
        return None, None
    try:
        res = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 15, "orientation": "landscape"},
            timeout=10,
        )
        if res.status_code == 200:
            videos = [v for v in res.json().get("videos", []) if (v.get("duration") or 0) <= 45]
            fresh = [v for v in videos if f"pv{v.get('id')}" not in used] or videos
            if fresh:
                chosen = random.choice(fresh)
                vid = f"pv{chosen.get('id')}"
                files = chosen.get("video_files", [])
                for vf in files:
                    if (vf.get("file_type") == "video/mp4" and vf.get("quality") == "hd"
                            and (vf.get("width") or 0) <= 1920):
                        return vid, vf.get("link")
                if files:
                    return vid, files[0].get("link")
    except Exception as e:
        print(f"Pexels Video hatası: {e}")
    return None, None


def _fetch_image(query: str, used: set):
    """(id, url). Önce Unsplash (aynı görsel gelirse 3 kez dener), sonra Pexels."""
    if UNSPLASH_ACCESS_KEY:
        for _ in range(3):
            try:
                res = requests.get(
                    "https://api.unsplash.com/photos/random",
                    params={"query": query, "orientation": "landscape", "client_id": UNSPLASH_ACCESS_KEY},
                    timeout=10,
                )
                if res.status_code != 200:
                    break
                data = res.json()
                pid = f"u{data.get('id')}"
                if pid in used:
                    continue
                try:
                    dl = data.get("links", {}).get("download_location")
                    if dl:
                        requests.get(dl, params={"client_id": UNSPLASH_ACCESS_KEY}, timeout=5)
                except Exception:
                    pass
                return pid, data["urls"]["regular"]
            except Exception as e:
                print(f"Unsplash hatası: {e}")
                break

    if PEXELS_API_KEY:
        try:
            res = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": 15},
                timeout=10,
            )
            if res.status_code == 200:
                photos = res.json().get("photos", [])
                fresh = [p for p in photos if f"pp{p.get('id')}" not in used] or photos
                if fresh:
                    chosen = random.choice(fresh)
                    return f"pp{chosen.get('id')}", chosen["src"]["large2x"]
        except Exception as e:
            print(f"Pexels hatası: {e}")

    return None, None


def fetch_hd_video_url(query: str = "nature landscape") -> str:
    """Eski imza: Pexels'ten HD MP4 linki ya da None."""
    return _pexels_video(query, set())[1]


def fetch_hd_image_url(query: str = "nature landscape"):
    """Eski imza: görsel linki ya da None."""
    return _fetch_image(query, set())[1]


def fetch_media(query: str, st: dict = None, specific: str = None):
    """(url, is_video). Önce konuya özel anahtar kelime (modelin verdiği, ör. 'humpback whale'), olmazsa kategori sorgusu.
    Her sorguda önce video, sonra resim aranır. st verilirse kullanılan medya kaydedilir ve tekrar seçilmez."""
    used = set(st.get("media_used", [])) if st is not None else set()
    for q in (specific, query):
        if not q:
            continue
        for fetcher, is_video in ((_pexels_video, True), (_fetch_image, False)):
            mid, url = fetcher(q, used)
            if url:
                if st is not None and mid:
                    st.setdefault("media_used", []).append(mid)
                return url, is_video
    return None, False


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
                       reply=None, delay_min: int = 3, thread=None) -> str:
    """reply: tek alt yorum (eski kullanım). thread: ek tweet listesi (mini thread). İkisi de ana tweetin altına zincirlenir."""
    due = (datetime.now(timezone.utc) + timedelta(minutes=delay_min)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    assets = ""
    metadata = ""

    # Video ise GraphQL nesnesi 'video', resim ise 'image' olur
    media_asset_key = "video" if is_video else "image"

    followups = ([reply] if reply else []) + [t for t in (thread or []) if t]
    if followups:
        first = "{ text: %s" % json.dumps(text, ensure_ascii=False)
        if media_url:
            first += f" assets: [{{ {media_asset_key}: {{ url: %s }} }}]" % json.dumps(media_url)
        first += " }"
        rest = " ".join("{ text: %s }" % json.dumps(t, ensure_ascii=False) for t in followups)
        metadata = "metadata: { twitter: { thread: [ %s %s ] } }" % (first, rest)
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


def post_to_x(text: str, media_url=None, is_video=False, reply=None, delay_min: int = 3, thread=None):
    """(başarı, sebep, alt_tweetler_gitti_mi). Sırayla dener: medya+alt tweetler -> medya -> sadece metin."""
    if not BUFFER_API_KEY:
        return False, "BUFFER_API_KEY eksik.", False
    try:
        channel_id = get_x_channel_id()
        followups = ([reply] if reply else []) + [t for t in (thread or []) if t]
        attempts = []
        if followups:
            attempts.append((media_url, followups))
        attempts.append((media_url, None))
        if media_url:
            attempts.append((None, None))

        last_error = None
        for med, fu in attempts:
            try:
                post_id = create_buffer_post(channel_id, text, med, is_video=is_video and bool(med),
                                             delay_min=delay_min, thread=fu)
                print(f"✅ Buffer'a eklendi. Post ID: {post_id} | Video: {is_video and bool(med)} | alt tweet: {len(fu or [])}")
                return True, "OK", bool(fu)
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
        "• Konu için Wikipedia'dan gerçek bir özet çekilir; Gemini/Groq/OpenRouter sadece o metindeki bilgiyle yazar.\n"
        "• İkinci bir model (farklı sağlayıcıdan) tweeti kaynağa karşı denetler ve ilk satıra 1-10 hook puanı verir; zayıfsa yeniden yazılır.\n"
        "• Görsel/video, modelin verdiği konuya özel anahtar kelimeyle (ör. humpback whale) Pexels/Unsplash'ten çekilir.\n"
        "• Tweet ve altındaki soru/kaynak linki Buffer üzerinden X'e iletilir.\n\n"
        "⚡ *Mevcut Komutlar:*\n"
        "• `/paylas` : Hemen bir tweet hazırlar ve Buffer'a ekler.\n"
        "• `/etkilesim` : Canlı linkler, tek dokunuşla takip bağlantıları ve 3 hazır yorum önerisi üretir.\n"
        "• `/cevap <gelen yorum>` : Gelen yoruma hazır cevap önerir.\n"
        "• `/yardim` : Bu yardım rehberini gösterir.\n\n"
        "🗓️ *Haftalık ritim:* Sabah günün serisi (Pzt Marine Monday, Sal Tree Tuesday, Çar Wild Wednesday, "
        "Per Feathered Thursday, Cum Flora Friday, Cmt Sky Saturday, Paz Small World Sunday). "
        "Akşam: Sal/Per/Cmt quiz, Çar myth vs fact, Paz mini thread, Pzt/Cum tek bilgi.\n"
        "🧠 *Quiz:* Cevap birkaç saat sonra ayrı tweet olarak çıkar.\n\n"
        "🔍 *İddia kontrolü:* Kaynakta olmayan sayı/isim/iddia varsa tweet paylaşılmaz, yenisi yazılır; hepsi şüpheli çıkarsa sana uyarı düşer.\n"
        "♻️ *Tekrar engeli:* Geçmiş tweetlere benzeyen içerik ve daha önce kullanılan kaynak/görsel tekrar seçilmez.\n"
        "📈 *Öğrenme:* X Analytics CSV'sini `python nature_bot.py --import-metrics dosya.csv` ile yüklersen bot en iyi giden "
        "konu ve hook kalıplarını daha sık seçer.\n\n"
        "🛡️ *Neden API Kredisi Harcanmaz?*\n"
        "Paylaşımlar Buffer API üzerinden yapıldığı için hesabın X API sınırlarına takılmaz ve tamamen ücretsizdir.\n\n"
        "🤖 *Hesabı otomatik olarak etiketle:* X > Ayarlar > Hesabın > Hesap bilgileri > Otomasyon.\n"
        f"Bio önerisi: `{BIO_SUGGESTION}`"
    )
    notify_telegram(help_text)


def send_interaction_reminder(tweet_text: str = None):
    """/etkilesim komutu çağrıldığında veya paylaşımdan sonra gecikmeyle tetiklenir.
    Beğeni/takip ELLE yapılır (otomatik beğeni/takip X kurallarına aykırıdır, hesap riski taşır);
    bot hazır yorum seçenekleri ve tek dokunuşluk linkleri verir."""
    context = tweet_text if tweet_text else "Nature, wildlife, and serene natural landscapes"
    prompt = (
        "Write 3 different short comments (each max 100 characters, no hashtags) that I can post on other popular "
        f"nature tweets. Topic context: '{context[:100]}'. Angles: 1) a thoughtful question, 2) a warm appreciation, "
        "3) a short curious reaction. Do not state any facts, numbers or names. "
        'Return ONLY valid JSON: {"comments": ["...", "...", "..."]}.'
    )
    data = call_llms_json(prompt, temperature=0.9, tier="fast")
    comments = []
    if data:
        comments = [str(c).strip().strip('"').replace("`", "'") for c in (data.get("comments") or [])]
        comments = [c for c in comments if 5 <= len(c) <= 140][:3]
    if not comments:
        comments = ["Incredible capture! Nature never ceases to amaze us. 🌿",
                    "This is why I love watching the natural world. 🍃",
                    "What a beautiful reminder of how much there is to discover. 🌍"]
    comment_lines = "\n".join(f"`{c}`" for c in comments)

    targets = random.sample(TARGET_ACCOUNTS, k=min(3, len(TARGET_ACCOUNTS)))
    follow_lines = "\n".join(f"• [@{a}](https://x.com/intent/follow?screen_name={a})" for a in targets)

    reminder_msg = (
        "🚀 *YARI OTOMATİK ETKİLEŞİM MODÜLÜ*\n\n"
        f"💡 *Önerilen Yorumlar (birini seç):*\n{comment_lines}\n\n"
        "1️⃣ *Canlı Doğa Akışı:*\n🔗 [Canlı #Nature Tweetleri](https://x.com/search?q=%23Nature%20OR%20%23Wildlife%20min_faves%3A20%20lang%3Aen%20-filter%3Areplies&f=live)\n"
        "_(İlk 2-3 tweet'i beğen ve yukarıdaki yorumlardan birini yaz; yeni atılmış tweetlere yorum daha çok görünür)_\n\n"
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
    if POST_MODE in ("series", "quiz", "random", "myth", "thread"):
        return POST_MODE
    if now.hour >= 16:
        wd = now.weekday()
        if wd in (1, 3, 5):   # Salı, Perşembe, Cumartesi akşamı quiz
            return "quiz"
        if wd == 2:           # Çarşamba akşamı myth vs fact
            return "myth"
        if wd == 6:           # Pazar akşamı mini thread
            return "thread"
        return "random"       # Pazartesi, Cuma akşamı tek bilgi
    return "series"


def build_content(mode: str, st: dict, now: datetime, cat=None, src=None, hook_style=None, feedback: str = "") -> dict:
    """Bir paylaşımın metnini hazırlar. Medya, metin kabul edildikten sonra çekilir."""
    c = {"mode": mode, "answer_post": None, "followups": [], "cat": None, "check_text": None,
         "keyword": None, "src": None, "hook_style": None, "family": None}
    if mode == "weather":
        c["text"] = get_weather_info()
        c["query"] = "morning sunrise nature"
        c["title"] = "☀️ Sabah Hava Durumu Buffer'a eklendi"
        c["err_title"] = "❌ Hava Durumu Hata:"
    elif mode == "quiz":
        quiz = generate_quiz(st, src, cat)
        c["src"] = src if quiz.get("used_src") else None
        c["text"] = format_quiz_tweet(quiz)
        c["answer_post"] = format_quiz_answer(quiz, c["src"]["url"] if c["src"] else None)
        c["check_text"] = (
            f"Quiz question: {quiz['q']}\n"
            + "\n".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(quiz["options"]))
            + f"\nMarked correct answer: {LETTERS[quiz['answer']]}) {quiz['options'][quiz['answer']]}\n"
            f"Explanation: {quiz['explain']}"
        )
        c["cat"] = quiz["cat"]
        c["keyword"] = quiz.get("keyword")
        c["query"] = TOPICS.get(quiz["cat"], TOPICS["animals"])[1]
        c["title"] = f"🧠 Quiz ({quiz['cat']}) Buffer'a eklendi"
        c["err_title"] = "❌ Quiz Hatası:"
    else:
        kind = mode if mode in ("series", "myth", "thread") else "fact"
        series = SERIES[now.weekday()] if kind == "series" else None
        post = generate_post(kind, cat, st, src, series, hook_style, feedback)
        c.update(text=post["text"], followups=post["followups"], cat=post["cat"], check_text=post["check_text"],
                 keyword=post["keyword"], src=post["src"], hook_style=post["hook_style"], family=post["family"])
        c["query"] = TOPICS[post["cat"]][1]
        if post["kind"] == "series" and series:
            label = series["name"]
        else:
            label = {"myth": "🔎 Myth vs Fact", "thread": "🧵 Thread"}.get(post["kind"], "İçerik")
        c["title"] = f"{label} ({post['cat']}) Buffer'a eklendi"
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

    # Tekrar / benzer / şüpheli içerik çıkarsa en fazla MAX_ATTEMPTS kez yeniden üret.
    #  - tekrar/benzer: yeni konu + yeni kaynak
    #  - şüpheli / zayıf hook: AYNI kaynakla, doğrulayıcının notlarıyla yeniden yaz (Shorts'taki review döngüsü)
    content = None
    best = None      # kapıları geçen en yüksek hook'lu taslak
    flagged = []     # (metin, sebepler)
    cat = src = hook_style = None
    feedback = ""
    fresh = True
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if fresh:
            cat = plan_category(mode, st, now)
            src = pick_source(cat, st) if cat else None
            hook_style = choose_hook_style(st)
            fresh = False
        cand = build_content(mode, st, now, cat, src, hook_style, feedback)
        feedback = ""
        if is_duplicate(st, cand["text"]):
            print(f"🔁 ({attempt}/{MAX_ATTEMPTS}) Aynı içerik daha önce paylaşılmış, yenisi üretiliyor...")
            fresh = True
            continue
        sim = find_similar(st, cand["text"])
        if sim:
            print(f"🔁 ({attempt}/{MAX_ATTEMPTS}) Geçmiş bir paylaşıma %{int(sim[0] * 100)} benziyor, yenisi üretiliyor...")
            fresh = True
            continue

        hook = None
        if FACT_CHECK and cand.get("check_text"):
            status, hook, issues = review_draft(cand["check_text"], cand.get("src"), cand.get("family"))
            if status == "suspicious":
                print(f"⚠️ ({attempt}/{MAX_ATTEMPTS}) İddia kontrolü şüpheli buldu: {issues}")
                flagged.append((cand["text"], issues))
                feedback = "The previous draft had these problems, fix them and stay strictly within the source: " + "; ".join(issues)
                continue
            if status == "unverified":
                if FACT_CHECK_STRICT:
                    print(f"⚠️ ({attempt}/{MAX_ATTEMPTS}) Doğrulanamadı, STRICT modda geçilmiyor.")
                    flagged.append((cand["text"], issues))
                    continue
                cand["verify_note"] = "⚠️ İddia kontrolü yapılamadı (doğrulayıcı model yanıt vermedi), elle bakmak isteyebilirsin."
            else:
                cand["verify_note"] = "🔍 İddia kontrolü: geçti ✅" + (f" | hook {hook}/10" if hook else "")

        cand["hook"] = hook
        if best is None or (hook or 0) > (best.get("hook") or 0):
            best = cand
        if hook is not None and hook < HOOK_MIN and attempt < MAX_ATTEMPTS:
            print(f"✍️ ({attempt}/{MAX_ATTEMPTS}) Hook zayıf ({hook}/10), daha çarpıcı yeniden yazılıyor...")
            feedback = (f"The previous draft's opening line scored only {hook}/10 for scroll-stopping power. "
                        "Rewrite it with a more specific, surprising first line. " + "; ".join(issues))
            continue
        content = best if (hook is not None and hook < HOOK_MIN) else cand
        break
    if content is None and best is not None:
        content = best
    if content is None:
        if flagged:
            lines = ["🛑 İddia kontrolü yüzünden bu tur paylaşım yapılmadı."]
            for t, iss in flagged[-2:]:
                lines.append(f"\n⚠️ Şüpheli tweet:\n{t}\nSebep: " + "; ".join(iss))
            notify_telegram("\n".join(lines))
            print("⏸️ Tüm denemeler şüpheli bulundu, bu tur atlandı.")
        else:
            print(f"⏸️ {MAX_ATTEMPTS} denemede de tekrar eden/benzer içerik çıktı, bu tur atlandı.")
            notify_telegram("⏸️ Tekrar eden veya geçmişe çok benzeyen içerik tespit edildi, bu tur paylaşım yapılmadı.")
        return True

    text = content["text"]
    followups = content["followups"]
    answer_post = content["answer_post"]
    err_title = content["err_title"]

    # Medya, METNİN gerçek konusuna göre çekilir: önce modelin verdiği özel anahtar kelime, olmazsa kategori sorgusu
    media_url, is_video = fetch_media(content["query"], st=st, specific=content.get("keyword"))
    media_type = "🎥 Video" if is_video else "📸 Görsel"
    title = f"{media_type} {content['title']}"

    # Her tweet tam aynı dakikada çıkmasın: Buffer gecikmesine 0..POST_JITTER_MAX dk eklenir
    delay = 3 + random.randint(0, max(0, POST_JITTER_MAX))
    success, reason, replied = post_to_x(text, media_url, is_video=is_video, delay_min=delay, thread=followups)

    if success:
        st.setdefault("recent_texts", []).append(text[:60])
        src_title = (content.get("src") or {}).get("title")
        if src_title:
            st.setdefault("used_sources", []).append(src_title)
        record_post(st, text, meta={"cat": content.get("cat"), "mode": mode, "hook_style": content.get("hook_style"),
                                    "hook": content.get("hook"), "source": src_title})

        msg = f"{title}\n\n{text}"
        if content.get("verify_note"):
            msg += f"\n\n{content['verify_note']}"
        if src_title:
            msg += f"\n📚 Kaynak: {src_title}"
        if followups:
            msg += "\n\n💬 Alt tweet(ler):\n" + "\n\n".join(f"↳ {f}" for f in followups)
            if not replied:
                msg += "\n\n⚠️ Alt tweet/yorum eklenemedi, sadece ana tweet gitti (loga bak)."

        # Quiz cevabı: birkaç saat sonra ayrı tweet olarak zamanlanır
        if answer_post:
            ok2, reason2, _ = post_to_x(answer_post, None, delay_min=QUIZ_ANSWER_DELAY_MIN)
            if ok2:
                msg += f"\n\n✅ Cevap tweeti {QUIZ_ANSWER_DELAY_MIN // 60} saat sonraya zamanlandı:\n{answer_post}"
            else:
                msg += f"\n\n⚠️ Cevap tweeti zamanlanamadı: {reason2}"
        notify_telegram(msg)

        # X içeriğini Instagram ve LinkedIn için ayrı, kopyalanabilir taslaklara dönüştür.
        # Bu taslaklar otomatik yayınlanmaz; Telegram'dan gözden geçirilip manuel kullanılabilir.
        try:
            from repurpose_content import make_platform_variants
            variants = make_platform_variants(content, _ask)
            repurpose_msg = (
                "📦 Çoklu platform içerik paketi (inceleme taslağı)\n\n"
                "📸 INSTAGRAM\n" + variants["instagram_caption"] +
                "\n\n💼 LINKEDIN\n" + variants["linkedin_post"]
            )
            notify_telegram(repurpose_msg)
            st.setdefault("repurposed_posts", []).append({
                "t": datetime.now(TZ).isoformat(),
                "source_text": text[:500],
                **variants,
            })
            st["repurposed_posts"] = st["repurposed_posts"][-50:]
            save_state(st)
        except Exception as e:
            print(f"Çoklu platform taslak üretimi atlandı: {str(e)[:180]}")

        # Hatırlatma, tweetin YAYINLANMASINDAN (Buffer gecikmesi dahil) ENGAGE_DELAY_SEC sonra gelir
        remind_after = ENGAGE_DELAY_SEC + delay * 60
        if SKIP_WAIT or ENGAGE_DELAY_SEC <= 0:
            print("⏭️ Etkileşim hatırlatması atlandı (SKIP_WAIT / ENGAGE_DELAY_SEC).")
        elif wait:
            print(f"⏳ Paylaşım yapıldı. Etkileşim bildirimi için {remind_after // 60} dk bekleniyor...")
            time.sleep(remind_after)
            send_interaction_reminder(text)
            print("✅ Yarı otomatik etkileşim bildirimi Telegram'a gönderildi.")
        elif background_reminder:
            timer = threading.Timer(remind_after, send_interaction_reminder, args=(text,))
            timer.daemon = True
            timer.start()
            print(f"⏳ Etkileşim hatırlatması {remind_after // 60} dk sonra için zamanlandı.")
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

    if "--import-metrics" in sys.argv:
        # Performans geri beslemesi: python nature_bot.py --import-metrics export.csv
        idx = sys.argv.index("--import-metrics")
        if idx + 1 >= len(sys.argv):
            print("Kullanım: python nature_bot.py --import-metrics dosya.csv")
            sys.exit(2)
        print(f"{import_metrics(sys.argv[idx + 1])} paylaşım metrikle eşleşti ve skorlandı.")
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
