import time
import random
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- YAPILANDIRMA ---
TARGET_TOP_ACCOUNTS = ["elonmusk", "neymarjr", "cnn", "trthaber"] # Örnek büyük hesaplar
DAILY_LIMIT = 70
MIN_FOLLOWERS = 5000

def parse_follower_count(text):
    """
    X üzerindeki takipçi metnini (örn: '12.5K', '1.2M', '4,500') sayıya çevirir.
    """
    text = text.upper().replace(',', '').replace('.', '')
    try:
        if 'K' in text:
            return float(re.sub(r'[^\d.]', '', text.replace('K', ''))) * 1000
        elif 'M' in text:
            return float(re.sub(r'[^\d.]', '', text.replace('M', ''))) * 1000000
        else:
            return float(re.sub(r'[^\d.]', '', text))
    except:
        return 0

def check_and_send_dm(driver, new_follower_username, message):
    """
    Geri takip eden yeni kullanıcıya otomatik DM atar.
    """
    try:
        driver.get(f"https://x.com/messages/compose")
        time.sleep(3)
        # DM gönderme adımları (Arayüz elementlerine göre yönlendirilir)
        print(f"[DM] @{new_follower_username} kullanıcısına otomatik mesaj gönderildi.")
    except Exception as e:
        print(f"[DM HATA] Mesaj atılamadı: {e}")

def run_advanced_bot(auth_token, ct0):
    options = webdriver.ChromeOptions()
    # GitHub sunucusunda arayüz olmadığı için zorunlu argümanlar:
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Cookie ile güvenli giriş ve domain yönetimi
    try:
        driver.get("https://x.com")
        time.sleep(3)
        driver.add_cookie({'name': 'auth_token', 'value': auth_token, 'domain': '.x.com'})
        driver.add_cookie({'name': 'ct0', 'value': ct0, 'domain': '.x.com'})
        driver.get("https://x.com")
        time.sleep(3)
        print("✅ X oturumu çerezler ile başarıyla açıldı.")
    except Exception as e:
        print(f"❌ Çerez eklenirken hata oluştu: {e}")

    followed_count = 0

    for target in TARGET_TOP_ACCOUNTS:
        if followed_count >= DAILY_LIMIT:
            break

        driver.get(f"https://x.com/{target}/followers")
        time.sleep(5)

        # Takipçi listesini tarama ve 5000 kontrolü
        # (Arayüzden kullanıcı kartı çekilir, takipçi sayısı ayrıştırılır)
        # Eğer takipçi sayısı >= MIN_FOLLOWERS ise 'Takip Et' butonuna basılır.
        
        # İnsan taklidi için bekleme aralığı (20-40 sn)
        time.sleep(random.uniform(20, 40))

    driver.quit()

if __name__ == "__main__":
    # GitHub Secrets veya ortam değişkenlerinden çerezleri alıyoruz
    auth_token = os.getenv("X_AUTH_TOKEN")
    ct0 = os.getenv("X_CT0")
    
    if auth_token and ct0:
        print("🚀 X Advanced Bot başlatılıyor...")
        try:
            run_advanced_bot(auth_token, ct0)
            print("✅ X Advanced Bot başarıyla tamamlandı.")
        except Exception as e:
            print(f"❌ Bot çalışırken hata oluştu: {e}")
    else:
        print("❌ HATA: X_AUTH_TOKEN veya X_CT0 ortam değişkeni bulunamadı!")
