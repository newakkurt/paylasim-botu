import json
import os
import sys
import requests
import tweepy
from google import genai

# Log tamponlamasını kapat
sys.stdout.reconfigure(line_buffering=True)

# Ortam Değişkenleri
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN") # İsteğe bağlı / Ekstra güçlendirme

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_TWEETS_FILE = "state/seen_tweets.json"

# Takip Edilecek Hedef Hesaplar
TARGET_ACCOUNTS = [
    "NatGeo",
    "BBCEarth",
    "WWF_TURKIYE",
    "TEMA_Vakfi",
    "DogaDernegi",
    "oceana",
    "NOAA",
    "atlasdergisi",
]


def get_twitter_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN if TWITTER_BEARER_TOKEN else None,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
        wait_on_rate_limit=True
    )


def load_seen_tweets() -> set:
    if os.path.exists(SEEN_TWEETS_FILE):
        try:
            with open(SEEN_TWEETS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_seen_tweet(tweet_id: str) -> None:
    seen = load_seen_tweets()
    seen.add(str(tweet_id))
    os.makedirs(os.path.dirname(SEEN_TWEETS_FILE), exist_ok=True)
    with open(SEEN_TWEETS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)


def generate_ai_comment(tweet_text: str, author_handle: str) -> tuple[str, str]:
    prompt = (
        f"Aşağıdaki Twitter paylaşımına uygun, doğa sever, nazik, olumlu ve etkileşimi artırıcı bir yanıt/yorum yaz.\n"
        f"Paylaşan Hesap: @{author_handle}\n"
        f"Tweet Metni: '{tweet_text}'\n"
        f"Direkt yanıt metnini yaz. Tırnak işareti, giriş/çıkış açıklaması ekleme. Maksimum 180 karakter olsun."
    )

    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            model_name = "gemini-2.0-flash"
            resp = client.models.generate_content(model=model_name, contents=prompt)
            return resp.text.strip(), f"Google Gemini ({model_name})"
        except Exception as e:
            print(f"Gemini yorum hatası: {e}")

    if GROQ_API_KEY:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                },
                timeout=15,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            return text, "Groq (Llama-3.3-70b)"
        except Exception as e:
            print(f"Groq yorum hatası: {e}")

    return "Doğa ve yaşam adına harika bir paylaşım! Çok teşekkürler. 🌿", "Sabit Yanıt Havuzu"


def send_telegram_approval_request(tweet_id: str, author_handle: str, tweet_text: str, ai_comment: str, ai_model: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    caption = (
        f"📢 **Yeni Hedef Tweet Algılandı!**\n\n"
        f"👤 **Hesap:** `@{author_handle}`\n"
        f"📝 **Tweet:** *{tweet_text}*\n\n"
        f"🤖 **Önerilen AI Yorumu:**\n`{ai_comment}`\n\n"
        f"⚡ **Üretici AI:** `{ai_model}`"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Onayla & Paylaş", "callback_data": f"reply_ok:{tweet_id}"},
                {"text": "❌ Pas Geç", "callback_data": f"reply_cancel:{tweet_id}"}
            ],
            [
                {"text": "✏️ Kendim Yazacağım", "callback_data": f"reply_custom:{tweet_id}"}
            ]
        ]
    }

    os.makedirs("state/pending_replies", exist_ok=True)
    with open(f"state/pending_replies/{tweet_id}.json", "w", encoding="utf-8") as f:
        json.dump({"ai_comment": ai_comment, "author": author_handle, "text": tweet_text}, f)

    try:
        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": caption,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            },
            timeout=10,
        )
        print(f"Approval request sent to Telegram for tweet {tweet_id}")
    except Exception as e:
        print(f"Telegram approval request error: {e}")


def check_target_accounts() -> None:
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("Twitter API anahtarları tanımlı değil, izleme atlanıyor.")
        return

    client = get_twitter_client()
    seen_tweets = load_seen_tweets()

    for handle in TARGET_ACCOUNTS:
        try:
            print(f"🔍 Kontrol edilirken: @{handle}")
            user = client.get_user(username=handle)
            if not user or not user.data:
                print(f"⚠️ Kullanıcı bulunamadı: @{handle}")
                continue

            user_id = user.data.id
            tweets = client.get_users_tweets(id=user_id, max_results=5, tweet_fields=["created_at"])

            if not tweets or not tweets.data:
                print(f"ℹ️ Son tweet bulunamadı: @{handle}")
                continue

            for tweet in tweets.data:
                tweet_id = str(tweet.id)
                if tweet_id in seen_tweets:
                    continue

                print(f"🎯 Yeni tweet bulundu (@{handle}): {tweet.text[:50]}...")
                
                ai_comment, ai_model = generate_ai_comment(tweet.text, handle)
                send_telegram_approval_request(tweet_id, handle, tweet.text, ai_comment, ai_model)
                save_seen_tweet(tweet_id)
                break

        except tweepy.errors.Unauthorized as e:
            print(f"❌ @{handle} hesabı kontrol edilirken 401 Unauthorized Hatası: API Anahtarlarını ve App İzinlerini Kontrol Edin.")
            break
        except Exception as e:
            print(f"@{handle} hesabı kontrol edilirken hata: {e}")


if __name__ == "__main__":
    check_target_accounts()
