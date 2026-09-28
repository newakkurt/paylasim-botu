"""
Telegram Kontrol Paneli - tamamen ücretsiz
----------------------------------------------
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


def commit_state() -> None:
    try:
        subprocess.run(["git", "config", "user.name", "telegram-control-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", STATE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Telegram offset güncellendi", "--allow-empty"], check=True)
    except subprocess.CalledProcessError as e:
        print("Durum commit edilemedi (kritik değil):", e)


def send_message(text: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=10,
    )


def get_updates(offset: int) -> list[dict]:
    resp = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
        params={"offset": offset, "timeout": 5},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


def run_script(script_name: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["python", script_name],
        capture_output=True, text=True, timeout=600,
    )
    success = result.returncode == 0
    output = result.stdout[-1500:] + "\n" + result.stderr[-1500:]
    return success, output


def main() -> None:
    offset = load_offset()
    updates = get_updates(offset)

    if not updates:
        print("Yeni mesaj yok.")
        return

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
    commit_state()


if __name__ == "__main__":
    main()
