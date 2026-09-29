import asyncio
import random
import os
import sys
from twikit import Client
from google import genai

# Log tamponlamasını kapat
sys.stdout.reconfigure(line_buffering=True)

# Ortam Değişkenleri
X_USERNAME = os.environ.get("X_USERNAME")
X_EMAIL = os.environ.get("X_EMAIL")
X_PASSWORD = os.environ.get("X_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Hedef Niş Hesaplar
TARGET_ACCOUNTS = ["NatGeo", "BBCEarth", "WWF_TURKIYE", "TEMA_Vakfi", "DogaDernegi", "NOAA"]

client = Client('en-US')

async def login():
    print("🔑 X hesabına giriş yapılıyor...")
    await client.login(
        auth_info_1=X_USERNAME,
        auth_info_2=X_EMAIL,
        password=X_PASSWORD
    )
    print("✅ Giriş başarılı.")

def generate_relevant_comment(tweet_text: str, author: str) -> str:
    """Tweet içeriğine tamamen alakalı olumlu ve yapıcı yorum üretir."""
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
        resp = ai_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
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
            tweets = await user.get_tweets('Tweets', count=3)
            
            if not tweets:
                continue

            for tweet in tweets:
                # 1. Alakalı Yorum Üret ve Yap
                comment = generate_relevant_comment(tweet.text, handle)
                print(f"💬 Yorum hazırlanıyor: {comment}")
                
                await tweet.reply(comment)
                print(f"✅ Yorum gönderildi -> @{handle}")
                
                # 2. İnsan Gibi Davran: 15-30 Dakika Rastgele Bekle (Radara Yakalanmama)
                sleep_minutes = random.randint(15, 30)
                print(f"⏳ Güvenlik için {sleep_minutes} dakika bekleniyor...")
                await asyncio.sleep(sleep_minutes * 60)
                break # Her hesaptan sadece 1 son tweete işlem yap
                
        except Exception as e:
            print(f"⚠️ @{handle} işlenirken hata veya limit: {e}")
            await asyncio.sleep(300) # Hata durumunda 5 dk bekle

if __name__ == "__main__":
    asyncio.run(run_bot())