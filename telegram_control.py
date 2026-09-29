"""
Telegram Kontrol Paneli - Render.com Ücretsiz Web Service Uyumlu (7/24 Aktif)
------------------------------------------------------------------------
"""

import json
import os
import subprocess
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

import requests


# UptimeRobot ve Render port taraması için hatasız HTTP sunucusu
class HealthCheckHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Bot 7/24 Aktif")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        return  # Log kirliliğini engelle


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🌐 HTTP Sunucusu {port} portunda başlatıldı.")
    server.serve_forever()


# HTTP sunucusunu arka plan thread'inde çalıştır
threading.Thread(target=run_dummy_server, daemon=True).start()


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram değişkenleri eksik.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("Telegram mesajı gönderilemedi:", e)


def get_updates(offset: int) -> list[dict]:
    if not TELEGRAM_BOT_TOKEN:
        return []
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
            continue

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
    
    while True:
        try:
            offset = process_updates(offset)
        except Exception as e:
            print("Döngü hatası:", e)
        time.sleep(2)


if __name__ == "__main__":
    main()
