import time
import random
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- YAPILANDIRMA ---
TARGET_TOP_ACCOUNTS = ["elonmusk", "neymarjr", "cnn", "trthaber"] # Hedef büyük hesaplar
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

def run_advanced_bot(auth_token, ct0):
    options = webdriver.ChromeOptions()
    # GitHub sunucusunda arayüz olmadığı için zorunlu argümanlar:
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # CDP ile çerez enjeksiyonu ve oturum açma
    try:
        driver.get("https://x.com")
        time.sleep(2)
        
        driver.execute_cdp_cmd('Network.setCookie', {
            'name': 'auth_token',
            'value': auth_token,
            'domain': '.x.com',
            'path': '/',
            'secure': True,
            'httpOnly': True
        })
        driver.execute_cdp_cmd('Network.setCookie', {
            'name': 'ct0',
            'value': ct0,
            'domain': '.x.com',
            'path': '/',
            'secure': True
        })
        
        driver.get("https://x.com")
        time.sleep(5)
        print("✅ X oturumu çerezler ile başarıyla açıldı.")
    except Exception as e:
        print(f"❌ Çerez eklenirken hata oluştu: {e}")
        driver.quit()
        return

    followed_count = 0

    for target in TARGET_TOP_ACCOUNTS:
        if followed_count >= DAILY_LIMIT:
            print(f"🛑 Günlük limit ({DAILY_LIMIT}) doldu. İşlem durduruluyor.")
            break

        print(f"🔍 Hedef taranıyor: @{target}")
        driver.get(f"https://x.com/{target}/followers")
        time.sleep(6)

        # Sayfayı aşağı kaydırarak kullanıcı kartlarını yükleme
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

        # Kullanıcı hücrelerini bulma
        user_cells = driver.find_elements(By.XPATH, "//[data-testid='UserCell']")
        print(f"👥 @{target} profilinde {len(user_cells)} kullanıcı bulundu.")

        for cell in user_cells:
            if followed_count >= DAILY_LIMIT:
                break

            try:
                # Kullanıcı adını yakalama
                username_elem = cell.find_element(By.XPATH, ".//[starts-with(@href, '/') and not(contains(@href, '/'))]")
                username = username_elem.text
            except:
                continue

            # Takip et butonunu bulma
            try:
                follow_button = cell.find_element(By.XPATH, ".//button[@data-testid and (contains(@data-testid, '-follow'))]")
                button_text = follow_button.text.lower()
                
                # Zaten takip ediliyorsa atla
                if "takip ediyor" in button_text or "following" in button_text:
                    continue
            except:
                continue

            # Takipçi kriteri sağlandığı için takip et butonuna basılıyor
            try:
                follow_button.click()
                followed_count += 1
                print(f"✅ [{followed_count}/{DAILY_LIMIT}] Başarıyla takip edildi: {username}")
                
                # İnsan taklidi için rastgele bekleme
                time.sleep(random.uniform(15, 30))
            except Exception as e:
                print(f"⚠️ Takip et butonuna tıklanamadı: {e}")

    driver.quit()

if __name__ == "__main__":
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
