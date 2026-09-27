"""
Doğa/Orman Bilgi Botu (Buffer sürümü — tamamen ücretsiz)
----------------------------------------------------------
Sabit bir bilgi havuzundan rastgele bir doğa/orman bilgisi seçer, Unsplash'ten
lisanslı bir fotoğraf linki bulur ve Buffer API üzerinden bağlı X hesabının
kuyruğuna ekler. Buffer, X'e gönderimi kendi üstleniyor — X'in ücretli
developer API'sine hiç ihtiyaç yok.

Gerekli ortam değişkenleri (.env.example dosyasına bak):
  BUFFER_API_KEY       - publish.buffer.com/settings/api adresinden alınır
  UNSPLASH_ACCESS_KEY  - unsplash.com/developers adresinden alınır
"""

import os
import random

import requests

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]

FACTS = [
    "Bir ağaç yılda ortalama 22 kilogram karbondioksit emer ve karşılığında oksijen üretir.",
    "Amazon Ormanları dünyadaki oksijenin yaklaşık %20'sini üretir, bu yüzden 'dünyanın akciğerleri' olarak anılır.",
    "Mantarlar, yer altında dev bir ağ oluşturarak ağaçların birbiriyle besin ve bilgi alışverişi yapmasını sağlar; buna 'orman interneti' denir.",
    "Sekoya ağaçları 100 metreyi aşan boylara ulaşabilir ve 3000 yıldan fazla yaşayabilir.",
    "Bir meşe ağacı, yaşamı boyunca yaklaşık 10 milyon adet meşe palamudu üretebilir.",
    "Orman toprağının sadece bir avucunda, dünya nüfusundan daha fazla mikroorganizma bulunur.",
    "Kelebekler ayaklarıyla tat alır; bir çiçeğe konduklarında onu ayaklarıyla 'tadarlar'.",
    "Baykuşlar boyunlarını 270 dereceye kadar çevirebilir çünkü göz küreleri hareket etmez.",
    "Bambü, dünyanın en hızlı büyüyen bitkisidir; bazı türleri günde 90 santimetre büyüyebilir.",
    "Bir karınca kendi ağırlığının 50 katına kadar yük taşıyabilir.",
    "Tundra bölgelerinde yaşayan ren geyikleri, gözlerinin rengini mevsime göre değiştirebilir.",
    "Deniz otu çayırları, tropik yağmur ormanlarından bile daha hızlı karbon depolayabilir.",
    "Ağaçlar birbirlerine kimyasal sinyaller göndererek zararlı böcek saldırılarına karşı komşularını uyarabilir.",
    "Dünyadaki tatlı suyun yaklaşık %20'si Amazon Nehri havzasından akar.",
    "Bal arıları, kovanlarına dönüş yolunu bulmak için Güneş'in konumunu pusula gibi kullanır.",
    "Kutup ayılarının derisi aslında siyahtır; kürkleri ışığı yansıttığı için beyaz görünür.",
    "Bir yağmur ormanı ağacının tepesindeki (kanopi) ekosistem, ormanın geri kalanından tamamen farklı canlı türlerine ev sahipliği yapar.",
    "Fillerin ayak tabanlarındaki hassas sinirler, kilometrelerce uzaktaki depremleri ve diğer fillerin ayak seslerini algılayabilir.",
    "Dünyadaki tüm canlı biyokütlenin yarısından fazlasını bitkiler oluşturur.",
    "Bazı orkide türleri, döllenmek için belirli bir arı türünü taklit edecek şekilde evrimleşmiştir.",
    "Bir orman yangınından sonra bazı çam kozalakları ancak yüksek ısıyla açılıp tohumlarını serbest bırakır.",
    "Ahtapotlar üç kalbe sahiptir; ikisi solungaçlara, biri vücudun geri kalanına kan pompalar.",
    "Yağmur ormanlarında, güneş ışığının toprağa ulaşması saatler sürebilir çünkü kat kat yaprak katmanlarından süzülür.",
    "Kunduzların yaptığı barajlar, zamanla küçük göller ve sulak alanlar oluşturarak yüzlerce türe yaşam alanı sağlar.",
    "Bazı ağaç türleri, kuraklık dönemlerinde köklerini kullanarak komşu ağaçlarla su paylaşabilir.",
    "Yarasalar, tozlaşmadan tohum yayılımına kadar birçok tropik bitkinin hayatta kalması için kritik öneme sahiptir.",
    "Bir orman ekosistemindeki yaprak döken bir ağaç, mevsim boyunca yaklaşık 200.000 yaprak dökebilir.",
    "Karıncalar, dünya üzerindeki toplam hayvan biyokütlesinin önemli bir kısmını oluşturur.",
    "Denizanaları 500 milyon yıldan uzun süredir var olan, dinozorlardan bile daha eski canlılardır.",
    "Bazı mantar türleri, tespit edilen en büyük ve en yaşlı canlı organizmalar arasındadır; bazıları binlerce dönümü kaplar.",
]


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
        "Buffer hesabına bağlı bir X/Twitter kanalı bulunamadı. "
        "Buffer'da X hesabını bağladığından emin ol."
    )


def get_random_fact() -> str:
    return random.choice(FACTS)


def get_unsplash_image_url(query: str = "forest nature") -> str:
    """Unsplash'ten lisanslı bir doğa fotoğrafının herkese açık linkini döndürür."""
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": query, "orientation": "landscape"},
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
    print("Kuyruğa eklendi:", result["post"])


def main() -> None:
    org_id = get_organization_id()
    channel_id = get_twitter_channel_id(org_id)
    text = get_random_fact()
    image_url = get_unsplash_image_url()
    create_post(channel_id, text, image_url)


if __name__ == "__main__":
    main()
