import time
import random
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- YAPILANDIRMA ---
TARGET_TOP_ACCOUNTS = ["elonmusk", "neymarjr", "cnn", "trthaber"]
DAILY_LIMIT = 70
MIN_FOLLOWERS = 5000  # Sadece 5000 ve üzeri takipçisi olan gerçek hesaplar

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
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

        user_cells = driver.find_elements(By.XPATH, "//*[@data-testid='UserCell']")
        print(f"👥 @{target} profilinde {len(user_cells)} kullanıcı bulundu.")

        usernames = []
        for cell in user_cells:
            try:
                username_elem = cell.find_element(By.XPATH, ".//a[@role='link']")
                href = username_elem.get_attribute("href")
                username = href.split("/")[-1]
                if username and username not in usernames:
                    usernames.append(username)
            except:
                continue

        for username in usernames:
            if followed_count >= DAILY_LIMIT:
                break

            try:
                # Kullanıcı profiline gidip takipçi sayısını doğrulama
                driver.get(f"https://x.com/{username}")
                time.sleep(3)

                # Profil sayfasından takipçi sayısını çekme
                follower_elem = driver.find_element(By.XPATH, "//a[contains(@href, '/verified_followers') or contains(@href, '/followers')]//span[1]")
                follower_text = follower_elem.text
                follower_count = parse_follower_count(follower_text)

                print(f"👤 @{username} | Takipçi: {follower_text}")

                if follower_count >= MIN_FOLLOWERS:
                    # Takip et butonunu bulma ve tıklama
                    try:
                        follow_button = driver.find_element(By.XPATH, "//button[@data-testid and (contains(@data-testid, '-follow'))]")
                        button_text = follow_button.text.lower()
                        
                        if "takip ediyor" in button_text or "following" in button_text:
                            print(f"ℹ️ Zaten takip ediliyor: @{username}")
                        else:
                            follow_button.click()
                            followed_count += 1
                            print(f"✅ [{followed_count}/{DAILY_LIMIT}] Başarıyla takip edildi: @{username} (Takipçi: {follower_text})")
                            time.sleep(random.uniform(15, 30))
                    except Exception as btn_err:
                        print(f"⚠️ Takip et butonu bulunamadı: {btn_err}")
                else:
                    print(f"⏩ Kriter altı hesap ({follower_count} < {MIN_FOLLOWERS}), atlanıyor: @{username}")

            except Exception as e:
                print(f"⚠️ @{username} incelenirken hata oluştu: {e}")
                continue

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
