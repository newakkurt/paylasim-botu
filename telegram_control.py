"""
Telegram Kontrol Paneli - Render.com Ücretsiz Web Service Uyumlu (7/24 Aktif)
------------------------------------------------------------------------------
Komutlar (Telegram'da bota mesaj olarak yaz):
  /paylas    -> normal bilgi + görsel paylaşımı (twitter_nature_bot.py)
  /hava      -> hava durumu paylaşımı (weather_bot.py)
  /video     -> doğa videosu paylaşımı (video_bot.py)
  /etkilesim -> günlük etkileşim önerisi (engagement_suggestions.py)
  /yardim    -> yardım mesajı
(/yardım, /etkileşim, /paylaş gibi Türkçe harfli yazımlar ve /komut@botadi da kabul edilir.)

Otomatik zamanlama:
  Her gün SCHEDULE'daki saatlerde ilgili script otomatik çalışır
  (günde sadece bir kez, tarih bazlı takip).
  twitter_nature_bot.py her paylaşımdan ENGAGE_DELAY_SEC (varsayılan 16 dk) sonra
  Telegram'a etkileşim hatırlatması gönderilir.

NOT: Bu dosya Render'da çalışır. GitHub Actions'ta çalıştırılırsa (telegram_control.yml)
hemen çıkar; çünkü sonsuz döngü Actions'ta her 10 dakikada üst üste binen işler yaratır
ve Render ile aynı token'ı dinleyip birbirinin güncellemesini bozar.
Zorla çalıştırmak istersen: FORCE_RUN=1
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# Actions koruması: Telegram dinleyicisi sadece 7/24 çalışan sunucuda (Render) olmalı.
if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("FORCE_RUN") != "1":
    print("ℹ️ telegram_control.py 7/24 çalışan sunucuda (Render) çalışır; GitHub Actions'ta atlandı.")
    sys.exit(0)

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


def keep_alive():
    """Render ücretsiz planı ~15 dk trafik görmezse servisi uyutur, uyuyan bot komutlara cevap vermez.
    Uyanıkken kendi dış adresine 10 dakikada bir istek atar. Zaten uyumuşsa kendini uyandıramaz;
    bunun için ayrıca UptimeRobot gibi bir dış ping kur (5 dk'da bir)."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        time.sleep(600)
        try:
            requests.get(url, timeout=15)
        except Exception as e:
            print("Keep-alive isteği başarısız:", e)


threading.Thread(target=keep_alive, daemon=True).start()


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state/telegram_offset.json"
SCHEDULE_STATE_FILE = "state/last_auto_posts.json"
STATS_FILE = "state/weekly_stats.json"

try:
    ENGAGE_DELAY_SEC = int(os.environ.get("ENGAGE_DELAY_SEC") or 960)
except ValueError:
    ENGAGE_DELAY_SEC = 960

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
    "🤝 Bilgi + görsel paylaşımından 16 dk sonra otomatik etkileşim hatırlatması gelir.\n"
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

HELP_COMMANDS = {"/yardim", "/start", "/help"}

# Türkçe harfleri ASCII'ye çevirir: /yardım -> /yardim, /etkileşim -> /etkilesim
_TR_MAP = str.maketrans({
    "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
})


def normalize_command(text: str) -> str:
    """'/Yardım@botadi arg' -> '/yardim'. Komut değilse boş string döner."""
    text = (text or "").strip()
    if not text.startswith("/"):
        return ""
    cmd = text.split()[0].split("@")[0]
    return cmd.translate(_TR_MAP).lower()


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
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096]},
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


def confirm_offset(offset: int) -> None:
    """Telegram'a 'offset'ten öncekileri aldım' der. Yeniden deploy olsa bile
    işlenmiş komutlar tekrar gelmez (offset dosyası Render'da kalıcı değil)."""
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params={"offset": offset, "limit": 1, "timeout": 0},
            timeout=10,
        )
    except Exception as e:
        print("Offset onaylanamadı:", e)


def run_script(script_name: str, extra_args: list[str] | None = None) -> tuple[bool, str]:
    env = os.environ.copy()
    if script_name == "twitter_nature_bot.py":
        # Script kendi içinde 16 dk uyumasın (aşağıdaki timeout 600 sn'de keserdi);
        # etkileşim hatırlatmasını bu süreç schedule_engagement_reminder() ile zamanlar.
        env["SKIP_WAIT"] = "1"
    try:
        result = subprocess.run(
            ["python", script_name] + (extra_args or []),
            capture_output=True, text=True, timeout=600, env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "Zaman aşımı: script 600 saniyede bitmedi."
    except Exception as e:
        return False, f"Script başlatılamadı: {type(e).__name__}: {e}"
    success = result.returncode == 0
    output = result.stdout[-1500:] + "\n" + result.stderr[-1500:]
    return success, output


def schedule_engagement_reminder() -> None:
    """twitter_nature_bot.py paylaşımından ENGAGE_DELAY_SEC sonra Telegram'a etkileşim hatırlatması yollar."""
    if ENGAGE_DELAY_SEC <= 0:
        return

    def _send():
        try:
            import twitter_nature_bot as nb
            nb.send_interaction_reminder()
        except Exception as e:
            print("Etkileşim hatırlatması gönderilemedi:", e)

    timer = threading.Timer(ENGAGE_DELAY_SEC, _send)
    timer.daemon = True
    timer.start()


def handle_command(cmd: str) -> None:
    if cmd in HELP_COMMANDS:
        send_message(HELP_TEXT)
        return

    script = COMMANDS.get(cmd)
    if not script:
        return

    send_message(f"⏳ Komut alındı: {cmd}\nÇalıştırılıyor: {script}")
    success, output = run_script(script)
    record_stat(script, success, trigger="manuel")
    if success:
        send_message(f"✅ Başarılı: {cmd} tamamlandı.")
        if script == "twitter_nature_bot.py":
            schedule_engagement_reminder()
    else:
        send_message(f"❌ Hata oluştu ({cmd}):\n{output.strip()[-900:]}")


def process_updates(offset: int) -> int:
    updates = get_updates(offset)
    if not updates:
        return offset

    new_offset = offset
    for update in updates:
        new_offset = update["update_id"] + 1
        # Komutu çalıştırmadan ÖNCE kaydet/onayla: script hata verse ya da zaman aşımına
        # uğrasa bile aynı komut tekrar tekrar çalışıp mükerrer paylaşım yapmasın.
        try:
            save_offset(new_offset)
        except OSError as e:
            print("Offset kaydedilemedi:", e)
        confirm_offset(new_offset)

        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        cmd = normalize_command(message.get("text", ""))

        if chat_id != str(TELEGRAM_CHAT_ID) or not cmd:
            continue

        try:
            handle_command(cmd)
        except Exception as e:
            print(f"Komut hatası ({cmd}):", e)
            send_message(f"❌ Komut hatası ({cmd}): {type(e).__name__}: {str(e)[:300]}")

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

        # Önce işaretle: script hata verse de aynı saat diliminde tekrar tekrar denenmesin
        state[state_key] = today_str
        save_schedule_state(state)

        extra_args = ["morning"] if (script == "weather_bot.py" and now.hour == 7) else None
        send_message(f"⏰ Otomatik paylaşım başlıyor ({now.hour}:00) → {script}")
        success, output = run_script(script, extra_args)
        record_stat(script, success, trigger="otomatik")
        send_message(f"✅ Paylaşıldı ({now.hour}:00)." if success else f"❌ Hata ({now.hour}:00):\n{output.strip()[-900:]}")
        if success and script == "twitter_nature_bot.py":
            schedule_engagement_reminder()


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
