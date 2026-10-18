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
MIN_FOLLOWERS = 5000  # Sadece 5000 ve üzeri takipçisi olan hesaplar takip edilir


def parse_follower_count(text):
    """
    X'teki takipçi metnini sayıya çevirir.
    Destekler: '12.5K', '1.2M', '12,5 B' (Türkçe bin), '1,2 Mn' (Türkçe milyon),
    '4,500', '4.500' ve sonuna eklenmiş 'Followers' / 'Takipçi' yazıları.
    """
    text = text.strip().upper().replace("\n", " ")
    m = re.match(r"([\d.,]+)\s*(MN|MİLYON|MILYON|BİN|BIN|K|M|B)?(?![A-ZÇĞİÖŞÜ])", text)
    if not m:
        # Ek yazı (Followers/Takipçi) yüzünden eşleşmediyse sadece sayıyı dene
        m = re.match(r"([\d.,]+)", text)
        if not m:
            return 0
        suffix = None
    else:
        suffix = m.group(2)

    num = m.group(1)
    try:
        if suffix:
            # Ondalık ayraç olarak nokta veya virgül gelebilir: 12.5K / 12,5 B
            value = float(num.replace(",", "."))
            if suffix in ("K", "B", "BIN", "BİN"):
                return value * 1_000
            return value * 1_000_000  # M, MN, MILYON
        # Ek yoksa ayraçlar binlik ayraçtır: 4,500 / 4.500
        return float(re.sub(r"[.,]", "", num))
    except ValueError:
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
    seen_usernames = set()  # Aynı hesabı iki kez incelememek için

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
                if username and username not in usernames and username not in seen_usernames:
                    usernames.append(username)
            except:
                continue

        for username in usernames:
            if followed_count >= DAILY_LIMIT:
                break

            seen_usernames.add(username)

            try:
                # Kullanıcı profiline gidip takipçi sayısını doğrulama
                driver.get(f"https://x.com/{username}")
                time.sleep(3)

                # Takipçi sayısı linki (tüm metni alıp parser'a veriyoruz)
                follower_elem = driver.find_element(
                    By.XPATH,
                    "//a[contains(@href, '/verified_followers') or contains(@href, '/followers')]"
                )
                follower_text = follower_elem.text.strip().replace("\n", " ")
                follower_count = parse_follower_count(follower_text)

                print(f"👤 @{username} | Takipçi: {follower_text} -> {int(follower_count)}")

                if follower_count >= MIN_FOLLOWERS:
                    # Takip et butonunu bulma ve tıklama
                    try:
                        # Sadece profil başlığındaki buton (yan paneldeki "Kimi takip etmeli"
                        # önerilerine yanlışlıkla tıklamamak için placementTracking içinde ara)
                        follow_button = driver.find_element(
                            By.XPATH,
                            "//div[@data-testid='placementTracking']//button[contains(@data-testid, '-follow')]"
                        )
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
                    print(f"⏩ Kriter altı hesap ({int(follower_count)} < {MIN_FOLLOWERS}), atlanıyor: @{username}")

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
