"""
Canlı Hava Durumu Botu (İstanbul) - tamamen ücretsiz
-------------------------------------------------------
Open-Meteo API (key gerektirmez, ücretsiz) ile İstanbul'un anlık hava
durumunu çeker, doğa temalı bir görselle Buffer üzerinden X + Instagram'a
paylaşır.
"""

import os
import random

import requests

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]

ISTANBUL_LAT = 41.0082
ISTANBUL_LON = 28.9784

BASE_HASHTAGS = "#doğa #nature #istanbul #havadurumu"

WEATHER_CODE_MAP = {
    0: ("Açık ve güneşli", "☀️"),
    1: ("Genel olarak açık", "🌤️"),
    2: ("Parçalı bulutlu", "⛅"),
    3: ("Kapalı", "☁️"),
    45: ("Sisli", "🌫️"),
    48: ("Kırağılı sis", "🌫️"),
    51: ("Hafif çisenti", "🌦️"),
    53: ("Orta çisenti", "🌦️"),
    55: ("Yoğun çisenti", "🌧️"),
    61: ("Hafif yağmurlu", "🌧️"),
    63: ("Orta şiddetli yağmur", "🌧️"),
    65: ("Şiddetli yağmur", "🌧️"),
    71: ("Hafif kar yağışlı", "🌨️"),
    73: ("Orta kar yağışlı", "🌨️"),
    75: ("Yoğun kar yağışlı", "❄️"),
    80: ("Sağanak yağmur", "🌦️"),
    81: ("Orta sağanak", "🌧️"),
    82: ("Şiddetli sağanak", "⛈️"),
    95: ("Gök gürültülü fırtına", "⛈️"),
}


def get_istanbul_weather() -> dict:
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": ISTANBUL_LAT,
            "longitude": ISTANBUL_LON,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Istanbul",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def format_weather_text(data: dict, greeting: bool = False) -> str:
    current = data["current"]
    daily = data["daily"]

    temp = round(current["temperature_2m"])
    feels_like = round(current["apparent_temperature"])
    humidity = current["relative_humidity_2m"]
    wind = round(current["wind_speed_10m"])
    code = current["weather_code"]
    condition, emoji = WEATHER_CODE_MAP.get(code, ("Değişken", "🌡️"))

    temp_max = round(daily["temperature_2m_max"][0])
    temp_min = round(daily["temperature_2m_min"][0])

    header = f"Günaydın! {emoji}\n\nİstanbul Hava Durumu\n\n" if greeting else f"{emoji} İstanbul Hava Durumu\n\n"

    text = (
        f"{header}"
        f"Şu an: {temp}°C (hissedilen {feels_like}°C)\n"
        f"Durum: {condition}\n"
        f"Bugün: {temp_min}°C - {temp_max}°C\n"
        f"Nem: %{humidity} | Rüzgar: {wind} km/s\n\n"
        f"{BASE_HASHTAGS}"
    )
    return text


def get_unsplash_image_url(query: str) -> str:
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": query, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["urls"]["regular"]


def pick_image_query(weather_code: int) -> str:
    if weather_code in (0, 1):
        return random.choice(["istanbul sunny sky", "clear sky nature"])
    if weather_code in (2, 3):
        return random.choice(["cloudy sky istanbul", "overcast nature"])
    if weather_code in (45, 48):
        return "foggy forest"
    if weather_code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return random.choice(["rain forest", "rainy istanbul"])
    if weather_code in (71, 73, 75):
        return "snow forest"
    if weather_code == 95:
        return "storm sky nature"
    return "istanbul nature"


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        BUFFER_API_URL,
        headers={"Authorization": f"Bearer {BUFFER_API_KEY}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=20,
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


def create_post(channel_id: str, text: str, image_url: str) -> None:
    data = buffer_graphql(
        """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id text } }
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
                "assets": [{"image": {"url": image_url}}],
            }
        },
    )
    result = data["createPost"]
    if "message" in result:
        raise RuntimeError(f"Post oluşturulamadı: {result['message']}")
    print("Hava durumu paylaşıldı:", result["post"])


def main() -> None:
    import sys
    greeting = len(sys.argv) > 1 and sys.argv[1] == "morning"

    weather_data = get_istanbul_weather()
    text = format_weather_text(weather_data, greeting=greeting)
    image_query = pick_image_query(weather_data["current"]["weather_code"])
    image_url = get_unsplash_image_url(image_query)

    org_id = get_organization_id()
    channels = get_channel_ids(org_id)

    if "twitter" in channels:
        create_post(channels["twitter"], text, image_url)
    if "instagram" in channels:
        create_post(channels["instagram"], text, image_url)


if __name__ == "__main__":
    main()
