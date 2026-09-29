import os
import random
import requests

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEARCH_TERMS = [
    "nature", "forest", "ocean", "waterfall", 
    "mountains", "wildlife", "rainforest", "landscape"
]

def fetch_pexels_video(query: str) -> str | None:
    if not PEXELS_API_KEY:
        print("PEXELS_API_KEY bulunamadı.")
        return None

    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=landscape"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        videos = data.get("videos", [])

        if not videos:
            return None

        selected_video = random.choice(videos)
        video_files = selected_video.get("video_files", [])

        # Telegram için en uygun çözünürlükteki SD/HD videoyu seç
        for vf in video_files:
            if vf.get("quality") == "sd" or (vf.get("width") and vf.get("width") <= 1280):
                return vf.get("link")

        return video_files[0].get("link") if video_files else None

    except Exception as e:
        print(f"Pexels video çekme hatası ({query}): {e}")
        return None


def download_and_send_telegram_video(video_url: str, caption: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram kimlik bilgileri eksik.")
        return False

    temp_filename = "temp_video.mp4"
    
    try:
        # 1. Videoyu geçici dosya olarak indir
        print("📥 Video indiriliyor...")
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(temp_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # 2. Telegram'a dosya yükleme (Multipart Form-Data) olarak gönder
        print("📤 Telegram'a dosya olarak yükleniyor...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        
        with open(temp_filename, "rb") as video_file:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
            }
            files = {"video": video_file}
            
            resp = requests.post(url, data=payload, files=files, timeout=60)
            resp.raise_for_status()
            
        print("✅ Video başarıyla Telegram'a gönderildi!")
        return True

    except Exception as e:
        print(f"Telegram video yükleme hatası: {e}")
        return False

    finally:
        # 3. İşlem bitince geçici dosyayı temizle
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


def main() -> None:
    print("🎬 Video bot çalıştırılıyor...")
    query = random.choice(SEARCH_TERMS)
    print(f"🔍 Pexels aranıyor: '{query}'")

    video_url = fetch_pexels_video(query)

    if not video_url:
        query = "nature"
        video_url = fetch_pexels_video(query)

    if not video_url:
        raise RuntimeError("Pexels API'den hiç video alınamadı.")

    caption = f"🌿 **Günün Doğa Videosu**\n\n🔍 *Arama Teması:* #{query}\n🎥 *Kaynak:* Pexels"
    
    success = download_and_send_telegram_video(video_url, caption)
    if not success:
        raise RuntimeError("Video Telegram'a iletilemedi.")


if __name__ == "__main__":
    main()
