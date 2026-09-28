"""
Doğa Videosu Botu (Pexels + Türkçe Seslendirme) - tamamen ücretsiz
----------------------------------------------------------------------
Pexels API'den (ücretsiz) daha önce kullanılmamış bir HD doğa videosu çeker,
gTTS ile Türkçe seslendirme ekler, videoyu repo'ya commit'leyip herkese açık
bir link üretir ve Buffer üzerinden X + Instagram'a paylaşır.

Gerekli ortam değişkenleri:
  BUFFER_API_KEY, PEXELS_API_KEY
  GITHUB_REPOSITORY - GitHub Actions içinde otomatik gelir
"""

import json
import os
import random
import subprocess
import tempfile

import requests
from gtts import gTTS

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")

STATE_FILE = "state/used_videos.json"
SEARCH_TERMS = ["forest", "ormanlar", "nature", "wildlife", "ocean waves", "mountains", "rainforest", "waterfall"]

NARRATIONS = [
    "Doğanın sessiz güzelliğine bir yolculuk. Ormanlar, dünyamızın en değerli hazinelerinden biridir.",
    "Her nefes, bir ağacın armağanıdır. Doğayı korumak, geleceğimizi korumaktır.",
    "Okyanuslar, gezegenimizin kalbidir. Onları korumak hepimizin görevi.",
    "Vahşi doğa, milyonlarca yıldır süren bir dengeyi barındırır. Bu dengeyi bozmamak elimizde.",
    "Dağlar, zamanın sessiz tanıklarıdır. Doğanın ihtişamını hep birlikte koruyalım.",
    "Yağmur ormanları, dünyanın akciğerleridir. Her ağaç, geleceğimiz için bir umut.",
]

WORK = tempfile.mkdtemp()


def load_used_ids() -> list[int]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_used_ids(ids: list[int]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(ids[-200:], f)  # son 200 videoyu hatırla, dosya şişmesin


def commit_state() -> None:
    try:
        subprocess.run(["git", "config", "user.name", "nature-video-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", STATE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Video döngüsü durumu güncellendi", "--allow-empty"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print("Durum commit edilemedi (kritik değil):", e)


def fetch_unused_pexels_video() -> dict:
    """Kullanılmamış bir Pexels HD doğa videosu bulana kadar arar."""
    used_ids = load_used_ids()

    for _ in range(10):  # en fazla 10 farklı arama denemesi
        query = random.choice(SEARCH_TERMS)
        page = random.randint(1, 5)
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "per_page": 15, "page": page, "orientation": "landscape"},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        random.shuffle(videos)
        for video in videos:
            if video["id"] not in used_ids:
                used_ids.append(video["id"])
                save_used_ids(used_ids)
                commit_state()
                return video

    raise RuntimeError("Kullanılmamış yeni bir Pexels videosu bulunamadı.")


def get_best_video_file(video: dict) -> str:
    """HD (1080p tercihen) mp4 dosya linkini seçer."""
    files = video["video_files"]
    hd_files = [f for f in files if f.get("quality") == "hd" and f.get("file_type") == "video/mp4"]
    candidates = hd_files or files
    candidates.sort(key=lambda f: f.get("width", 0), reverse=True)
    return candidates[0]["link"]


def make_narration() -> str:
    text = random.choice(NARRATIONS)
    path = os.path.join(WORK, "narration.mp3")
    gTTS(text=text, lang="tr").save(path)
    return path, text


def download_file(url: str, dest: str) -> None:
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def get_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def merge_audio_into_video(video_path: str, audio_path: str) -> str:
    """Videonun orijinal sesini kısar, üzerine Türkçe seslendirmeyi bindirir.
    Video, seslendirmeden uzunsa video süresine, kısaysa seslendirme süresine göre kesilir."""
    video_duration = get_duration(video_path)
    audio_duration = get_duration(audio_path)
    final_duration = min(video_duration, audio_duration + 1.0)

    output_path = os.path.join(WORK, "final.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-t", str(final_duration),
            "-filter_complex", "[0:a]volume=0.15[bg];[bg][1:a]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264", "-c:a", "aac",
            output_path,
        ],
        check=True, capture_output=True,
    )
    return output_path


def commit_video_and_get_url(video_path: str) -> str:
    dest_dir = "videos"
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, "latest_nature_video.mp4")
    subprocess.run(["cp", video_path, dest_path], check=True)

    subprocess.run(["git", "config", "user.name", "nature-video-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", dest_path], check=True)
    subprocess.run(["git", "commit", "-m", "Yeni doğa videosu", "--allow-empty"], check=True)
    subprocess.run(["git", "push"], check=True)

    return f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/{dest_path}"


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        BUFFER_API_URL,
        headers={"Authorization": f"Bearer {BUFFER_API_KEY}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"Buffer API hatası: {data['errors']}")
    return data["data"]


def get_organization_id() -> str:
    data = buffer_graphql("query { account { organizations { id } } }")
    return data["account"]["organizations"][0]["id"]


def get_channel_ids(organization_id: str) -> dict[str, str]:
    data = buffer_graphql(
        """
        query GetChannels($organizationId: OrganizationId!) {
          channels(input: { organizationId: $organizationId }) {
            id
            service
          }
        }
        """,
        {"organizationId": organization_id},
    )
    channels: dict[str, str] = {}
    for ch in data["channels"]:
        service = "twitter" if ch["service"] == "x" else ch["service"]
        channels[service] = ch["id"]
    return channels


def create_video_post(channel_id: str, text: str, video_url: str) -> None:
    data = buffer_graphql(
        """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id } }
            ... on MutationError { message }
          }
        }
        """,
        {
            "input": {
                "text": text,
                "channelId": channel_id,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "assets": [{"video": {"url": video_url}}],
            }
        },
    )
    result = data["createPost"]
    if "message" in result:
        raise RuntimeError(f"Video post oluşturulamadı: {result['message']}")
    print("Video paylaşıldı:", result["post"])


def main() -> None:
    video_data = fetch_unused_pexels_video()
    video_file_url = get_best_video_file(video_data)

    raw_video_path = os.path.join(WORK, "raw.mp4")
    download_file(video_file_url, raw_video_path)

    narration_path, narration_text = make_narration()
    final_video_path = merge_audio_into_video(raw_video_path, narration_path)
    public_url = commit_video_and_get_url(final_video_path)

    caption = narration_text + "\n\n#doğa #nature #forest #wildlife"

    org_id = get_organization_id()
    channels = get_channel_ids(org_id)

    if "twitter" in channels:
        create_video_post(channels["twitter"], caption, public_url)
    if "instagram" in channels:
        create_video_post(channels["instagram"], caption, public_url)


if __name__ == "__main__":
    main()
