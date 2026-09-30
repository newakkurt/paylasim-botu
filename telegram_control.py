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
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from zoneinfo import ZoneInfo
    ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
except Exception:
    # Sunucuda tzdata bulunamazsa (nadir durum) sabit UTC+3'e düş.
    # Türkiye DST kullanmıyor, bu yüzden sabit +3 her zaman doğru.
    ISTANBUL_TZ = timezone(timedelta(hours=3))

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
STATS_FILE = "state/weekly_stats.json"

HELP_TEXT = (
    "🌿 Doğa Paylaşım Botu - Komutlar\n\n"
    "/paylas — Bilgi + görsel paylaşımı yapar (X + Instagram)\n"
    "/hava — Anlık İstanbul hava durumu paylaşır\n"
    "/video — Pexels'ten tekrarsız HD doğa videosu paylaşır\n"
    "/etkilesim — Günlük etkileşim önerisi (hesap listesi + örnek yorumlar)\n"
    "/yardim — Bu mesajı gösterir\n\n"
    "🕐 Otomatik günlük akış:\n"
    "07:00 — Hava durumu (Günaydın)\n"
    "09:00 — Etkileşim önerisi\n"
    "11:00, 14:00 — Bilgi + görsel paylaşımı\n"
    "16:00, 21:00 — Video paylaşımı\n\n"
    "📊 Pazar günleri haftalık özet rapor otomatik gelir."
)

# Otomatik günlük paylaşım saatleri (İstanbul saatiyle, 24 saat formatında)
# Günde 5 paylaşım: 07 hava (Günaydın), 11-14 görsel, 16-21 video
SCHEDULE = {
    "weather_bot.py": [7],
    "twitter_nature_bot.py": [11, 14],
    "video_bot.py": [16, 21],
    "engagement_suggestions.py": [9],  # sabah 9'da günlük etkileşim önerisi
}

COMMANDS = {
    "/paylas": "twitter_nature_bot.py",
    "/hava": "weather_bot.py",
    "/video": "video_bot.py",
    "/etkilesim": "engagement_suggestions.py",
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


def load_stats() -> list[dict]:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def record_stat(script: str, success: bool, trigger: str) -> None:
    """Her paylaşım denemesini (otomatik ya da manuel) kaydeder. Son 60
    kayıt tutulur, dosya şişmesin (haftalık rapor için fazlasıyla yeterli)."""
    stats = load_stats()
    stats.append({
        "date": str(datetime.now(ISTANBUL_TZ).date()),
        "script": script,
        "success": success,
        "trigger": trigger,  # "otomatik" | "manuel"
    })
    stats = stats[-60:]
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)


def build_weekly_report() -> str:
    stats = load_stats()
    cutoff = datetime.now(ISTANBUL_TZ).date() - timedelta(days=7)
    recent = [s for s in stats if date.fromisoformat(s["date"]) >= cutoff]

    if not recent:
        return "📊 Haftalık Rapor\n\nBu hafta hiç kayıtlı paylaşım bulunamadı."

    by_script: dict[str, dict[str, int]] = {}
    for s in recent:
        entry = by_script.setdefault(s["script"], {"başarılı": 0, "başarısız": 0})
        entry["başarılı" if s["success"] else "başarısız"] += 1

    names = {
        "twitter_nature_bot.py": "📝 Bilgi + Görsel Paylaşımı",
        "weather_bot.py": "🌤️ Hava Durumu",
        "video_bot.py": "🎬 Video",
        "engagement_suggestions.py": "🤝 Etkileşim Önerisi",
    }

    lines = ["📊 Haftalık Özet Rapor\n"]
    total_success = 0
    total_fail = 0
    for script, counts in by_script.items():
        label = names.get(script, script)
        lines.append(f"{label}: {counts['başarılı']} başarılı, {counts['başarısız']} başarısız")
        total_success += counts["başarılı"]
        total_fail += counts["başarısız"]

    lines.append(f"\nToplam: {total_success} başarılı paylaşım, {total_fail} hata")
    lines.append("\n💡 Takipçi ve etkileşim büyümesini X'in kendi analytics sayfasından kontrol etmeyi unutma.")

    return "\n".join(lines)


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

        if text == "/yardim":
            send_message(HELP_TEXT)
            continue

        if text in COMMANDS:
            script = COMMANDS[text]
            send_message(f"⏳ Komut alındı: {text}\nÇalıştırılıyor: {script}")
            success, output = run_script(script)
            record_stat(script, success, trigger="manuel")
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
    now = datetime.now(ISTANBUL_TZ)
    today_str = str(now.date())
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
        record_stat(script, success, trigger="otomatik")
        send_message(f"✅ Paylaşıldı ({now.hour}:00)." if success else f"❌ Hata ({now.hour}:00):\n{output[:500]}")

        state[state_key] = today_str
        save_schedule_state(state)


WEEKLY_REPORT_HOUR = 20  # Pazar günü saat 20:00'de haftalık rapor


def check_weekly_report() -> None:
    now = datetime.now(ISTANBUL_TZ)
    if now.weekday() != 6:  # Python'da Pazar = 6
        return
    if now.hour != WEEKLY_REPORT_HOUR:
        return

    today_str = str(now.date())
    state = load_schedule_state()
    if state.get("weekly_report_date") == today_str:
        return  # bugün zaten gönderildi

    send_message(build_weekly_report())
    state["weekly_report_date"] = today_str
    save_schedule_state(state)


def main() -> None:
    print("🤖 Telegram Kontrol Botu başlatıldı. Komutlar dinleniyor...")
    offset = load_offset()

    while True:
        try:
            offset = process_updates(offset)
            check_daily_auto_posts()
            check_weekly_report()
        except Exception as e:
            print("Döngü hatası:", e)
        time.sleep(60)  # her dakika kontrol yeterli


if __name__ == "__main__":
    main()
