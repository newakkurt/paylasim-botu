"""
Telegram Kontrol Paneli - Render.com Ücretsiz Web Service Uyumlu (7/24 Aktif)
------------------------------------------------------------------------------
Komutlar (Telegram'da bota mesaj olarak yaz):
  /paylas -> normal bilgi + görsel paylaşımı (twitter_nature_bot.py)
  /hava   -> hava durumu paylaşımı (weather_bot.py)
  /video  -> doğa videosu paylaşımı (video_bot.py)

Otomatik zamanlama:
  Her gün MORNING_WEATHER_HOUR'da hava durumu, EVENING_VIDEO_HOUR'da video
  otomatik paylaşılır (günde sadece bir kez, tarih bazlı takip).
"""

import json
import os
import subprocess
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# Render'ın port kontrolünü geçmek için ücretsiz sahte HTTP sunucusu
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active 24/7!")

    def log_message(self, format, *args):
        return


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()


threading.Thread(target=run_dummy_server, daemon=True).start()


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state/telegram_offset.json"
SCHEDULE_STATE_FILE = "state/last_auto_posts.json"

# Otomatik günlük paylaşım saatleri (İstanbul saatiyle, 24 saat formatında)
# Günde 5 paylaşım: 07 hava (Günaydın), 11-14 görsel, 16-21 video
SCHEDULE = {
    "weather_bot.py": [7],
    "twitter_nature_bot.py": [11, 14],
    "video_bot.py": [16, 21],
}

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


def load_schedule_state() -> dict:
    if os.path.exists(SCHEDULE_STATE_FILE):
        try:
            with open(SCHEDULE_STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_schedule_state(state: dict) -> None:
    os.makedirs(os.path.dirname(SCHEDULE_STATE_FILE), exist_ok=True)
    with open(SCHEDULE_STATE_FILE, "w") as f:
        json.dump(state, f)


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


def run_script(script_name: str, extra_args: list[str] | None = None) -> tuple[bool, str]:
    result = subprocess.run(
        ["python", script_name] + (extra_args or []),
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


def check_daily_auto_posts() -> None:
    """SCHEDULE sözlüğündeki her script için, belirlenen saatlerde günde
    tam olarak bir kez otomatik paylaşım tetiklenir (saat+tarih bazlı takip,
    aynı saat diliminde tekrar tekrar tetiklenmez)."""
    now = datetime.now()
    today_str = str(date.today())
    state = load_schedule_state()

    for script, hours in SCHEDULE.items():
        if now.hour not in hours:
            continue
        state_key = f"{script}_{now.hour}"
        if state.get(state_key) == today_str:
            continue  # bu saat diliminde bugün zaten paylaşıldı

        extra_args = ["morning"] if (script == "weather_bot.py" and now.hour == 7) else None
        send_message(f"⏰ Otomatik paylaşım başlıyor ({now.hour}:00) → {script}")
        success, output = run_script(script, extra_args)
        send_message(f"✅ Paylaşıldı ({now.hour}:00)." if success else f"❌ Hata ({now.hour}:00):\n{output[:500]}")

        state[state_key] = today_str
        save_schedule_state(state)


def main() -> None:
    print("🤖 Telegram Kontrol Botu başlatıldı. Komutlar dinleniyor...")
    offset = load_offset()

    while True:
        try:
            offset = process_updates(offset)
            check_daily_auto_posts()
        except Exception as e:
            print("Döngü hatası:", e)
        time.sleep(60)  # her dakika kontrol yeterli


if __name__ == "__main__":
    main()
