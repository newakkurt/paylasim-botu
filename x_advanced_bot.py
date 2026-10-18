import time
import random
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- YAPILANDIRMA ---
TARGET_TOP_ACCOUNTS = ["elonmusk", "neymarjr", "cnn", "trthaber"]
DAILY_LIMIT = 70
MIN_FOLLOWERS = 5000  # Sadece 5000 ve üzeri takipçisi olan hesaplar takip edilir
PAGE_WAIT = 20        # Profil elemanları için maksimum bekleme (sn)

FOLLOWERS_LINK_XPATH = (
    "//a[contains(@href, '/verified_followers') or "
    "substring(@href, string-length(@href) - 9) = '/followers']"
)


def parse_follower_count(text):
    """
    X'teki takipçi metnini sayıya çevirir.
    Destekler: '12.5K', '1.2M', '12,5 B' (Türkçe bin), '1,2 Mn' (Türkçe milyon),
    '4,500', '4.500' ve sonuna eklenmiş 'Followers' / 'Takipçi' yazıları.
    """
    text = text.strip().upper().replace("\n", " ")
    m = re.match(r"([\d.,]+)\s*(MN|MİLYON|MILYON|BİN|BIN|K|M|B)?(?![A-ZÇĞİÖŞÜ])", text)
    if not m:
        m = re.match(r"([\d.,]+)", text)
        if not m:
            return 0
        suffix = None
    else:
        suffix = m.group(2)

    num = m.group(1)
    try:
        if suffix:
            value = float(num.replace(",", "."))
            if suffix in ("K", "B", "BIN", "BİN"):
                return value * 1_000
            return value * 1_000_000  # M, MN, MILYON
        return float(re.sub(r"[.,]", "", num))
    except ValueError:
        return 0


def debug_page(driver, username):
    """Hata anında sayfada ne olduğunu loga yazar."""
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.replace("\n", " | ")[:250]
    except Exception:
        body = "(body okunamadı)"
    print(f"🧪 DEBUG @{username} | url={driver.current_url} | title={driver.title} | body={body}")


def get_follower_text(driver, username):
    """
    Profile gider, takipçi linkini gerçekten görünene kadar bekler.
    Bulamazsa sayfayı bir kez yenileyip tekrar dener. Bulamazsa None döner.
    """
    for attempt in (1, 2):
        driver.get(f"https://x.com/{username}")
        try:
            elem = WebDriverWait(driver, PAGE_WAIT).until(
                EC.presence_of_element_located((By.XPATH, FOLLOWERS_LINK_XPATH))
            )
            # Metin render olana kadar kısa bekleme
            for _ in range(10):
                text = elem.text.strip().replace("\n", " ")
                if text:
                    return text
                time.sleep(0.5)
        except Exception:
            if attempt == 1:
                print(f"🔄 @{username} yeniden deneniyor...")
                continue
            debug_page(driver, username)
    return None


def find_header_follow_button(driver):
    """
    SADECE açık olan profilin kendi takip butonunu döndürür.
    - Yan paneli (sidebarColumn) ve öneri kartlarını (UserCell) dışarıda bırakır.
    - Butonun data-testid'sindeki kullanıcı ID'sini profilin gerçek ID'si ile doğrular.
    """
    buttons = driver.find_elements(
        By.XPATH,
        "//div[@data-testid='primaryColumn']"
        "//button[contains(@data-testid, '-follow') or contains(@data-testid, '-unfollow')]"
        "[not(ancestor::*[@data-testid='UserCell'])]"
    )
    if not buttons:
        return None

    user_id = None
    try:
        ld = driver.find_element(By.XPATH, "//script[@type='application/ld+json']").get_attribute("innerHTML")
        m = re.search(r'"identifier"\s*:\s*"?(\d+)"?', ld)
        if m:
            user_id = m.group(1)
    except Exception:
        pass

    for b in buttons:
        tid = b.get_attribute("data-testid") or ""
        if user_id and not tid.startswith(user_id + "-"):
            continue
        return b
    return None


def run_advanced_bot(auth_token, ct0):
    options = webdriver.ChromeOptions()
    # GitHub sunucusunda arayüz olmadığı için zorunlu argümanlar:
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    # Masaüstü görünümü zorla (küçük pencerede X mobil/kısıtlı arayüz gösterebiliyor)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

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
    seen_usernames = set()

    for target in TARGET_TOP_ACCOUNTS:
        if followed_count >= DAILY_LIMIT:
            print(f"🛑 Günlük limit ({DAILY_LIMIT}) doldu. İşlem durduruluyor.")
            break

        print(f"🔍 Hedef taranıyor: @{target}")
        driver.get(f"https://x.com/{target}/followers")
        time.sleep(6)

        # Sayfayı aşağı kaydırarak kullanıcı kartlarını yükleme
        for _ in range(4):
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
                follower_text = get_follower_text(driver, username)
                if not follower_text:
                    print(f"⚠️ @{username} takipçi sayısı okunamadı (gizli/askıda/yüklenmedi), atlanıyor.")
                    continue

                follower_count = parse_follower_count(follower_text)
                print(f"👤 @{username} | Takipçi: {follower_text} -> {int(follower_count)}")

                if follower_count >= MIN_FOLLOWERS:
                    try:
                        # Sadece bu profilin kendi butonu (yan panel/öneriler hariç, ID doğrulamalı)
                        follow_button = WebDriverWait(driver, 10).until(
                            lambda d: find_header_follow_button(d)
                        )
                        tid = follow_button.get_attribute("data-testid") or ""

                        if tid.endswith("-unfollow"):
                            print(f"ℹ️ Zaten takip ediliyor: @{username}")
                        elif not tid.endswith("-follow"):
                            print(f"ℹ️ Takip edilebilir durumda değil (@{username}): {tid}")
                        else:
                            follow_button.click()
                            followed_count += 1
                            print(f"✅ [{followed_count}/{DAILY_LIMIT}] Başarıyla takip edildi: @{username} (Takipçi: {follower_text})")
                            time.sleep(random.uniform(15, 30))
                    except Exception as btn_err:
                        print(f"⚠️ Takip et butonu bulunamadı (@{username}): {str(btn_err)[:120]}")
                else:
                    print(f"⏩ Kriter altı hesap ({int(follower_count)} < {MIN_FOLLOWERS}), atlanıyor: @{username}")

            except Exception as e:
                print(f"⚠️ @{username} incelenirken hata oluştu: {str(e)[:150]}")
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
