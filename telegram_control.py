"""
Telegram Kontrol Paneli & Inline Buton Dinleyici - Render.com Uyumlu
------------------------------------------------------------------
"""

import json
import os
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

import requests
import tweepy

# Unbuffered output (Log tamponlamasını kapat)
sys.stdout.reconfigure(line_buffering=True)

# Ortam Değişkenleri
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET", "")

STATE_FILE = "state/telegram_offset.json"

COMMANDS = {
    "/paylas": "twitter_nature_bot.py",
    "/hava": "weather_bot.py",
    "/video": "video_bot.py",
    "/izle": "twitter_monitor.py",
}


# --- Render Web Service Sunucusu ---
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
        return


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🌐 HTTP Sunucusu {port} portunda başlatıldı.", flush=True)
    server.serve_forever()


threading.Thread(target=run_dummy_server, daemon=True).start()


# --- Twitter Yanıt Gönderme ---
def post_twitter_reply(tweet_id: str, reply_text: str) -> tuple[bool, str]:
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return False, "Twitter API bilgileri eksik."

    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        response = client.create_tweet(
            in_reply_to_tweet_id=tweet_id,
            text=reply_text
        )
        return True, f"Tweet ID: {response.data['id']}"
    except Exception as e:
        return False, str(e)


# --- Helper Fonksiyonlar ---
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
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("Telegram mesaj hatası:", e, flush=True)


def answer_callback_query(callback_query_id: str, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("Callback yanıt hatası:", e, flush=True)


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
        print("Updates hatası:", e, flush=True)
        return []


def run_script(script_name: str) -> tuple[bool, str]:
    # python -u parametresi ile çıktıların anlık yakalanması sağlanır
    result = subprocess.run(
        ["python", "-u", script_name],
        capture_output=True, text=True, timeout=600,
    )
    success = result.returncode == 0
    
    out = result.stdout.strip() if result.stdout else ""
    err = result.stderr.strip() if result.stderr else ""
    
    combined_output = out
    if err:
        if combined_output:
            combined_output += "\n\n⚠️ Hata/Uyarı Logları:\n" + err
        else:
            combined_output = err

    if not combined_output:
        combined_output = "Betik herhangi bir konsol çıktısı üretmedi."

    return success, combined_output


# --- Telegram Güncellemelerini İşleme ---
def process_updates(offset: int) -> int:
    updates = get_updates(offset)
    if not updates:
        return offset

    new_offset = offset
    for update in updates:
        new_offset = update["update_id"] + 1

        # 1. Buton Tıklamaları (Inline Callback Queries)
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            data = cb.get("data", "")
            chat_id = str(cb.get("from", {}).get("id", ""))

            if chat_id != str(TELEGRAM_CHAT_ID):
                continue

            if ":" in data:
                action, tweet_id = data.split(":", 1)
                pending_file = f"state/pending_replies/{tweet_id}.json"

                if action == "reply_ok":
                    if os.path.exists(pending_file):
                        with open(pending_file, "r", encoding="utf-8") as f:
                            info = json.load(f)
                        ai_comment = info.get("ai_comment", "")
                        
                        answer_callback_query(cb_id, "🚀 Twitter'a yanıt gönderiliyor...")
                        success, res = post_twitter_reply(tweet_id, ai_comment)
                        
                        if success:
                            send_message(f"✅ **Yorum Twitter'da Paylaşıldı!**\n\n💬 `{ai_comment}`\n🔗 {res}")
                            if os.path.exists(pending_file):
                                os.remove(pending_file)
                        else:
                            send_message(f"❌ **Twitter Paylaşım Hatası:**\n{res}")
                    else:
                        answer_callback_query(cb_id, "⚠️ Bu talebin süresi dolmuş veya dosya bulunamadı.")

                elif action == "reply_cancel":
                    answer_callback_query(cb_id, "Pas geçildi.")
                    send_message(f"🗑️ Tweet yanıtı pas geçildi (Tweet ID: `{tweet_id}`).")
                    if os.path.exists(pending_file):
                        os.remove(pending_file)

                elif action == "reply_custom":
                    answer_callback_query(cb_id, "Özel yanıt modu seçildi.")
                    send_message(f"✏️ **Özel Yanıt Modu:**\nTweet ID: `{tweet_id}` için yanıtınızı başında `reply:{tweet_id}:` belirterek yazın.\n\n*Örnek:* `reply:{tweet_id}: Harika bir doğa manzarası!`")

        # 2. Normal Metin Komutları ve Özel Yanıtlar
        elif "message" in update:
            message = update.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "").strip()

            if chat_id != str(TELEGRAM_CHAT_ID):
                continue

            # Özel Yanıt Kontrolü (reply:tweet_id:metin)
            if text.startswith("reply:"):
                parts = text.split(":", 2)
                if len(parts) == 3:
                    _, tweet_id, custom_text = parts
                    send_message(f"⏳ Özel yanıtınız Twitter'a iletiliyor: `{custom_text.strip()}`")
                    success, res = post_twitter_reply(tweet_id, custom_text.strip())
                    if success:
                        send_message(f"✅ **Özel Yanıtınız Twitter'da Paylaşıldı!**\n🔗 {res}")
                        pending_file = f"state/pending_replies/{tweet_id}.json"
                        if os.path.exists(pending_file):
                            os.remove(pending_file)
                    else:
                        send_message(f"❌ **Özel Yanıt Paylaşılamadı:**\n{res}")

            # Normal Komutlar
            elif text.lower() in COMMANDS:
                cmd = text.lower()
                script = COMMANDS[cmd]
                send_message(f"⏳ Komut alındı: {cmd}\nÇalıştırılıyor: {script}")
                success, output = run_script(script)
                
                # Çıktı logunu Telegram'a iletme
                if success:
                    send_message(f"✅ **Başarılı: {cmd} tamamlandı.**\n\n📄 **Çıktı Logu:**\n```\n{output[:3500]}\n```")
                else:
                    send_message(f"❌ **Hata oluştu ({cmd}):**\n\n📄 **Loglar:**\n```\n{output[:3500]}\n```")

    save_offset(new_offset)
    return new_offset


def main() -> None:
    print("🤖 Telegram Kontrol & Onay Botu Başlatıldı...", flush=True)
    offset = load_offset()
    
    while True:
        try:
            offset = process_updates(offset)
        except Exception as e:
            print("Döngü hatası:", e, flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
