import asyncio
import json
import os
import random
import sys
from google import genai
from twikit import Client

sys.stdout.reconfigure(line_buffering=True)

X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
X_COOKIES_JSON = os.environ.get("X_COOKIES_JSON")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TARGET_ACCOUNTS = [
    "NatGeo",
    "BBCEarth",
    "WWF_TURKIYE",
    "TEMA_Vakfi",
    "DogaDernegi",
    "NOAA",
]
COOKIES_FILE = "cookies.json"

client = Client("en-US")


async def login():
    print("🔑 X oturumu kontrol ediliyor...")

    # 1. Öncelik: Render Environment içindeki X_COOKIES_JSON metni
    if X_COOKIES_JSON and X_COOKIES_JSON.strip():
        try:
            cookies_dict = json.loads(X_COOKIES_JSON.strip())
            client.set_cookies(cookies_dict)
            print("✅ Environment 'X_COOKIES_JSON' üzerinden oturum yüklendi.")
            return
        except Exception as e:
            print(f"⚠️ Environment cookies okuma hatası: {e}")

    # 2. Öncelik: Dosya bazlı cookies.json
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                cookies_dict = json.load(f)
                client.set_cookies(cookies_dict)
                print("✅ Yerel 'cookies.json' dosyasından oturum yüklendi.")
                return
        except Exception as e:
            print(f"⚠️ Dosya cookies okuma hatası: {e}")

    # 3. Öncelik: Klasik Giriş
    print("⚠️ Geçerli çerez bulunamadı, kullanıcı bilgileriyle giriş deneniyor...")
    try:
        await client.login(
            auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD
        )
        cookies = client.get_cookies()
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f)
        print("✅ Kullanıcı bilgileriyle giriş başarılı, yeni cookies.json kaydedildi.")
    except Exception as e:
        print(f"❌ Giriş hatası: {e}")
        raise e


def generate_relevant_comment(tweet_text: str, author: str) -> str:
    prompt = (
        f"Sen tutkulu bir doğa ve okyanus fotoğrafçısısın. "
        f"@{author} hesabının şu paylaşımına içten, olumlu, yapıcı ve alakalı bir Türkçe yorum yaz:\n\n"
        f"Tweet: '{tweet_text}'\n\n"
        f"Kurallar:\n"
        f"- Maksimum 120 karakter olsun.\n"
        f"- Reklam, link veya bot gibi görünen ifadeler içermesin.\n"
        f"- Samimi ve doğasever bir üslup kullan."
    )
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        resp = ai_client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        return resp.text.strip()
    except Exception as e:
        print(f"AI yorum üretim hatası: {e}")
        return "Doğanın mükemmelliğini ve bu harika açıları görmek ilham verici! 🌿"


async def run_bot():
    await login()

    for handle in TARGET_ACCOUNTS:
        try:
            print(f"\n🔍 @{handle} hesabı inceleniyor...")
            user = await client.get_user_by_screen_name(handle)
            tweets = await user.get_tweets("Tweets", count=3)

            if not tweets:
                continue

            for tweet in tweets:
                comment = generate_relevant_comment(tweet.text, handle)
                print(f"💬 Yorum hazırlanıyor: {comment}")

                await tweet.reply(comment)
                print(f"✅ Yorum gönderildi -> @{handle}")

                sleep_minutes = random.randint(15, 30)
                print(f"⏳ Güvenlik için {sleep_minutes} dakika bekleniyor...")
                await asyncio.sleep(sleep_minutes * 60)
                break

        except Exception as e:
            print(f"⚠️ @{handle} işlenirken hata: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_bot())
