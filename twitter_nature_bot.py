import sys

sys.stdout.reconfigure(line_buffering=True)

async def login():
    print("🔑 X oturumu kontrol ediliyor...")

    # 1. Öncelik: Render Environment içindeki X_COOKIES_JSON
    if X_COOKIES_JSON and X_COOKIES_JSON.strip():
        try:
            raw_cookies = json.loads(X_COOKIES_JSON.strip())

            # Liste formatındaysa {"name": "value"} sözlüğüne dönüştür
            if isinstance(raw_cookies, list):
                cookies_dict = {
                    cookie["name"]: cookie["value"]
                    for cookie in raw_cookies
                    if "name" in cookie and "value" in cookie
                }
            else:
                cookies_dict = raw_cookies

            client.set_cookies(cookies_dict)
            print("✅ Environment 'X_COOKIES_JSON' üzerinden oturum yüklendi.")
            return
        except Exception as e:
            print(f"⚠️ Environment cookies okuma hatası: {e}")

    # 2. Öncelik: Yerel cookies.json dosyası
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                raw_cookies = json.load(f)
                if isinstance(raw_cookies, list):
                    cookies_dict = {
                        cookie["name"]: cookie["value"]
                        for cookie in raw_cookies
                        if "name" in cookie and "value" in cookie
                    }
                else:
                    cookies_dict = raw_cookies

                client.set_cookies(cookies_dict)
                print("✅ Yerel 'cookies.json' dosyasından oturum yüklendi.")
                return
        except Exception as e:
            print(f"⚠️ Dosya cookies okuma hatası: {e}")

    # 3. Öncelik: Kullanıcı bilgileriyle giriş
    print("⚠️ Geçerli çerez bulunamadı, kullanıcı bilgileriyle giriş deneniyor...")
    await client.login(
        auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD
    )
