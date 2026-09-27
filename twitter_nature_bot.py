import os
import random
import time
import requests
from google import genai

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

HASHTAGS = "#doğa #orman #nature #forest #earth"

# Unsplash araması için geniş doğa konuları havuzu
NATURE_KEYWORDS = [
    "forest",
    "rainforest",
    "wildlife",
    "waterfall",
    "nature landscape",
    "mountains",
    "pine trees",
    "jungle",
    "autumn forest",
    "green nature",
]


def generate_nature_fact() -> str:
    """Google Gemini API kullanarak benzersiz ve taze bir doğa bilgisi üretir (Hata korumalı)."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = (
        "Doğa, ormanlar, bitkiler veya orman canlıları hakkında ilginç, az bilinen, "
        "merak uyandırıcı 1 adet Türkçe bilgi yaz. "
        "Direkt bilgi cümlesiyle başla. Giriş/çıkış açıklamaları yapma, tırnak işareti kullanma. "
        "Uzunluğu maksimum 200 karakter olsun."
    )
    
    # Denenecek model öncelik sırası
    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        for attempt in range(3):  # Her model için 3 kere dene
            try:
                print(f"Gemini isteği gönderiliyor: Model={model_name}, Deneme={attempt + 1}")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                print(f"Gemini API uyarısı ({model_name}): {e}")
                time.sleep(3)  # 503 yoğunluk hatası durumunda 3 saniye bekle
                
    raise RuntimeError("Gemini API tüm denemelere rağmen yanıt veremedi.")


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        BUFFER_API_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"Buffer API hatası: {data['errors']}")
    return data["data"]


def get_organization_id() -> str:
    data = buffer_graphql(
        "query GetOrganizations { account { organizations { id name } } }"
    )
    orgs = data["account"]["organizations"]
    if not orgs:
        raise RuntimeError("Buffer hesabında hiç organizasyon bulunamadı.")
    return orgs[0]["id"]


def get_twitter_channel_id(organization_id: str) -> str:
    data = buffer_graphql(
        """
        query GetChannels($organizationId: OrganizationId!) {
          channels(input: { organizationId: $organizationId }) {
            id
            name
            service
          }
        }
        """,
        {"organizationId": organization_id},
    )
    for ch in data["channels"]:
        if ch["service"] in ("twitter", "x"):
            return ch["id"]
    raise RuntimeError(
        "Buffer hesabına bağlı bir X/Twitter kanalı bulunamadı."
    )


def get_unsplash_image_url() -> str:
    """NATURE_KEYWORDS havuzundan rastgele bir kelime seçerek HD doğa fotoğrafı çeker."""
    selected_query = random.choice(NATURE_KEYWORDS)
    print(f"Unsplash araması yapılıyor: '{selected_query}'")
    
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": selected_query, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["urls"]["regular"]


def create_post(channel_id: str, text: str, image_url: str) -> None:
    data = buffer_graphql(
        """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post { id text dueAt }
            }
            ... on MutationError {
              message
            }
          }
        }
        """,
        {
            "input": {
                "text": text,
                "channelId": channel_id,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "assets": [{"image": {"url": image_url}}],
            }
        },
    )
    result = data["createPost"]
    if "message" in result:
        raise RuntimeError(f"Post oluşturulamadı: {result['message']}")
    print("Paylaşıldı:", result["post"])


def main() -> None:
    org_id = get_organization_id()
    channel_id = get_twitter_channel_id(org_id)
    
    # Gemini ile taze bilgi üretimi
    fact = generate_nature_fact()
    text = fact + "\n\n" + HASHTAGS
    
    # Rastgele doğa konusuna göre HD Unsplash görseli çekimi
    image_url = get_unsplash_image_url()
    
    create_post(channel_id, text, image_url)


if __name__ == "__main__":
    main()
