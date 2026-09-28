"""
Telegram Kontrol Paneli - Render.com Uyumlu (7/24 Aktif)
--------------------------------------------------
Telegram botuna gelen komut mesajlarını kontrol eder, tanıdığı bir komut
görürse ilgili paylaşım scriptini hemen çalıştırır.

Komutlar (Telegram'da bota mesaj olarak yaz):
  /paylas        -> normal bilgi + görsel paylaşımı (twitter_nature_bot.py)
  /hava          -> hava durumu paylaşımı (weather_bot.py)
  /video         -> doğa videosu paylaşımı (video_bot.py)

Gerekli ortam değişkenleri:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import json
import os
import subprocess
import time

import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state/telegram_offset.json"

COMMANDS = {
    "/paylas": "twitter_nature_bot.py",
    "/hava": "weather_bot.py",
    "/video": "video_bot.py",
}


def load_offset() -> int:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f).get("offset", 0)
        except (json.JSONDecodeError, OSError):
            pass
    return 0


def save_offset(offset: int) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"offset": offset}, f)


def send_message(text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("Telegram mesajı gönderilemedi:", e)


def get_updates(offset: int) -> list[dict]:
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 10},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        print("Telegram updates alınırken hata oluştu:", e)
        return []


def run_script(script_name: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["python", script_name],
        capture_output=True, text=True, timeout=600,
    )
    success = result.returncode == 0
    output = result.stdout[-1500:] + "\n" + result.stderr[-1500:]
    return success, output


def process_updates(offset: int) -> int:
    updates = get_updates(offset)
    if not updates:
        return offset

    new_offset = offset
    for update in updates:
        new_offset = update["update_id"] + 1
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip().lower()

        if chat_id != str(TELEGRAM_CHAT_ID):
            continue  # sadece yetkili chat'ten gelen komutları işle

        if text in COMMANDS:
            script = COMMANDS[text]
            send_message(f"⏳ Komut alındı: {text}\nÇalıştırılıyor: {script}")
            success, output = run_script(script)
            if success:
                send_message(f"✅ Başarılı: {text} tamamlandı.")
            else:
                send_message(f"❌ Hata oluştu ({text}):\n{output[:500]}")

    save_offset(new_offset)
    return new_offset


def main() -> None:
    print("🤖 Telegram Kontrol Botu başlatıldı. Komutlar dinleniyor...")
    offset = load_offset()
    
    # Render üzerinde sürekli çalışması için sonsuz döngü (Polling)
    while True:
        try:
            offset = process_updates(offset)
        except Exception as e:
            print("Döngü hatası:", e)
        time.sleep(2)  # Sunucuyu yormamak için her kontrol arası 2 saniye bekle


if __name__ == "__main__":
    main()
