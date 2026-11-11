"""Fetch a vertical Pexels clip and upload it as a YouTube Short."""
from __future__ import annotations
import os
import random
import tempfile
from pathlib import Path
import requests

PEXELS_API_KEY = (os.getenv("PEXELS_API_KEY") or "").strip()
YOUTUBE_CLIENT_ID = (os.getenv("YOUTUBE_CLIENT_ID") or "").strip()
YOUTUBE_CLIENT_SECRET = (os.getenv("YOUTUBE_CLIENT_SECRET") or "").strip()
YOUTUBE_REFRESH_TOKEN = (os.getenv("YOUTUBE_REFRESH_TOKEN") or "").strip()
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
SEARCH_TERMS = ["forest", "ocean waves", "waterfall", "wildlife", "mountains", "rainforest", "flowers"]
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024

def fetch_portrait_video(query: str) -> dict:
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY GitHub Actions secret eksik.")
    response = requests.get("https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": 30, "orientation": "portrait"}, timeout=25)
    response.raise_for_status()
    candidates = []
    for video in response.json().get("videos", []):
        if int(video.get("duration") or 0) > 180:
            continue
        files = [item for item in video.get("video_files", [])
            if item.get("link") and int(item.get("height") or 0) > int(item.get("width") or 0)]
        if not files:
            continue
        suitable = [item for item in files if 720 <= int(item.get("width") or 0) <= 1080]
        chosen = max(suitable or files, key=lambda item: int(item.get("width") or 0))
        candidates.append({"id": video.get("id"), "url": chosen["link"],
            "width": chosen.get("width"), "height": chosen.get("height")})
    if not candidates:
        raise RuntimeError(f"Pexels '{query}' aramasında 3 dakikadan kısa dikey video bulunamadı.")
    return random.choice(candidates)

def download_video(url: str) -> str:
    response = requests.get(url, stream=True, timeout=45)
    response.raise_for_status()
    temp = tempfile.NamedTemporaryFile(prefix="nature_short_", suffix=".mp4", delete=False)
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise RuntimeError("Video 100 MB sınırını aştı; daha küçük bir klip seçin.")
            temp.write(chunk)
        temp.close()
        if total == 0:
            raise RuntimeError("Pexels boş video dosyası döndürdü.")
        return temp.name
    except Exception:
        temp.close()
        Path(temp.name).unlink(missing_ok=True)
        raise

def build_youtube_service():
    missing = [name for name, value in (
        ("YOUTUBE_CLIENT_ID", YOUTUBE_CLIENT_ID),
        ("YOUTUBE_CLIENT_SECRET", YOUTUBE_CLIENT_SECRET),
        ("YOUTUBE_REFRESH_TOKEN", YOUTUBE_REFRESH_TOKEN)) if not value]
    if missing:
        raise RuntimeError("YouTube OAuth GitHub Actions secrets eksik: " + ", ".join(missing))
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("YouTube bağımlılıkları kurulu değil; requirements.txt yüklemesini kontrol edin.") from exc
    credentials = Credentials(token=None, refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token", client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET, scopes=[YOUTUBE_SCOPE])
    credentials.refresh(Request())
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)

def upload_short(video_path: str, query: str, pexels_id: int | str, dry_run: bool = False) -> str | None:
    service = build_youtube_service()
    channel_response = service.channels().list(part="id,snippet", mine=True).execute()
    channels = channel_response.get("items", [])
    if not channels:
        raise RuntimeError("OAuth hesabına bağlı YouTube kanalı bulunamadı.")
    channel = channels[0]
    print(f"YouTube kanalı doğrulandı: {channel.get('snippet', {}).get('title', 'kanal')} ({channel.get('id')})")
    title = f"{query.title()} in Nature 🌿 #Shorts"[:100]
    description = (f"A short moment from the natural world: {query}.\n\n"
        f"Footage source: Pexels (video ID {pexels_id}).\n"
        "Follow for more nature and wildlife moments.\n\n#Shorts #Nature #Wildlife")
    if dry_run:
        print("DRY RUN: Video YouTube'a yüklenmedi.")
        return None
    from googleapiclient.http import MediaFileUpload
    privacy = (os.getenv("YOUTUBE_PRIVACY_STATUS") or "public").strip().lower()
    if privacy not in ("public", "unlisted", "private"):
        raise RuntimeError("YOUTUBE_PRIVACY_STATUS public, unlisted veya private olmalı.")
    request = service.videos().insert(part="snippet,status", body={
        "snippet": {"title": title, "description": description,
            "tags": ["Shorts", "Nature", "Wildlife", query.replace(" ", "")],
            "categoryId": "15", "defaultLanguage": "en"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }, media_body=MediaFileUpload(video_path, mimetype="video/mp4",
        resumable=True, chunksize=8 * 1024 * 1024))
    result = request.execute()
    video_id = result.get("id")
    if not video_id:
        raise RuntimeError("YouTube API yanıtında video ID bulunamadı; yükleme doğrulanamadı.")
    print(f"YOUTUBE_PUBLISHED id={video_id} url=https://www.youtube.com/shorts/{video_id}")
    return video_id

def main() -> None:
    dry_run = (os.getenv("DRY_RUN") or "").strip().lower() in ("1", "true", "yes")
    query = random.choice(SEARCH_TERMS)
    video = fetch_portrait_video(query)
    print(f"Pexels dikey video bulundu: {video['width']}x{video['height']} (ID: {video['id']})")
    path = download_video(video["url"])
    try:
        upload_short(path, query, video["id"], dry_run=dry_run)
    finally:
        Path(path).unlink(missing_ok=True)

if __name__ == "__main__":
    main()
