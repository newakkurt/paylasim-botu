"""
Doğa/Orman Bilgi Botu (Buffer sürümü — tamamen ücretsiz)
----------------------------------------------------------
Geniş bir bilgi havuzundan, TEKRARSIZ bir döngüyle (kullanılanları hatırlayan
bir durum dosyasıyla) bir doğa/orman bilgisi seçer, Unsplash'ten lisanslı bir
fotoğraf linki bulur ve Buffer API üzerinden bağlı X hesabına anında paylaşır.
"""

import json
import os
import random
import subprocess

import requests

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")

STATE_FILE = "state/used_facts.json"
HASHTAGS = "#doğa #orman #doğasever #nature #forest #wildlife #naturelovers #earth"

FACTS = [
    "Bir ağaç yılda ortalama 22 kilogram karbondioksit emer ve karşılığında oksijen üretir.",
    "Amazon Ormanları dünyadaki oksijenin yaklaşık %20'sini üretir, bu yüzden 'dünyanın akciğerleri' olarak anılır.",
    "Mantarlar, yer altında dev bir ağ oluşturarak ağaçların birbiriyle besin ve bilgi alışverişi yapmasını sağlar; buna 'orman interneti' denir.",
    "Sekoya ağaçları 100 metreyi aşan boylara ulaşabilir ve 3000 yıldan fazla yaşayabilir.",
    "Bir meşe ağacı, yaşamı boyunca yaklaşık 10 milyon adet meşe palamudu üretebilir.",
    "Orman toprağının sadece bir avucunda, dünya nüfusundan daha fazla mikroorganizma bulunur.",
    "Kelebekler ayaklarıyla tat alır; bir çiçeğe konduklarında onu ayaklarıyla tadarlar.",
    "Baykuşlar boyunlarını 270 dereceye kadar çevirebilir çünkü göz küreleri hareket etmez.",
    "Bambü, dünyanın en hızlı büyüyen bitkisidir; bazı türleri günde 90 santimetre büyüyebilir.",
    "Bir karınca kendi ağırlığının 50 katına kadar yük taşıyabilir.",
    "Tundra bölgelerinde yaşayan ren geyikleri, gözlerinin rengini mevsime göre değiştirebilir.",
    "Deniz otu çayırları, tropik yağmur ormanlarından bile daha hızlı karbon depolayabilir.",
    "Ağaçlar birbirlerine kimyasal sinyaller göndererek zararlı böcek saldırılarına karşı komşularını uyarabilir.",
    "Dünyadaki tatlı suyun yaklaşık %20'si Amazon Nehri havzasından akar.",
    "Bal arıları, kovanlarına dönüş yolunu bulmak için Güneş'in konumunu pusula gibi kullanır.",
    "Kutup ayılarının derisi aslında siyahtır; kürkleri ışığı yansıttığı için beyaz görünür.",
    "Bir yağmur ormanı ağacının tepesindeki kanopi ekosistemi, ormanın geri kalanından tamamen farklı canlı türlerine ev sahipliği yapar.",
    "Fillerin ayak tabanlarındaki hassas sinirler, kilometrelerce uzaktaki depremleri ve diğer fillerin ayak seslerini algılayabilir.",
    "Dünyadaki tüm canlı biyokütlenin yarısından fazlasını bitkiler oluşturur.",
    "Bazı orkide türleri, döllenmek için belirli bir arı türünü taklit edecek şekilde evrimleşmiştir.",
    "Bir orman yangınından sonra bazı çam kozalakları ancak yüksek ısıyla açılıp tohumlarını serbest bırakır.",
    "Ahtapotlar üç kalbe sahiptir; ikisi solungaçlara, biri vücudun geri kalanına kan pompalar.",
    "Yağmur ormanlarında, güneş ışığının toprağa ulaşması saatler sürebilir çünkü kat kat yaprak katmanlarından süzülür.",
    "Kunduzların yaptığı barajlar, zamanla küçük göller ve sulak alanlar oluşturarak yüzlerce türe yaşam alanı sağlar.",
    "Bazı ağaç türleri, kuraklık dönemlerinde köklerini kullanarak komşu ağaçlarla su paylaşabilir.",
    "Yarasalar, tozlaşmadan tohum yayılımına kadar birçok tropik bitkinin hayatta kalması için kritik öneme sahiptir.",
    "Bir orman ekosistemindeki yaprak döken bir ağaç, mevsim boyunca yaklaşık 200 bin yaprak dökebilir.",
    "Karıncalar, dünya üzerindeki toplam hayvan biyokütlesinin önemli bir kısmını oluşturur.",
    "Denizanaları 500 milyon yıldan uzun süredir var olan, dinozorlardan bile daha eski canlılardır.",
    "Bazı mantar türleri, tespit edilen en büyük ve en yaşlı canlı organizmalar arasındadır; bazıları binlerce dönümü kaplar.",
    "Zürafaların dilleri mor-siyah renktedir; bilim insanları bunun güneş yanığından koruduğunu düşünüyor.",
    "Bir tek balina, yaşamı boyunca karbondioksit tutma açısından binlerce ağaca bedel olabilir.",
    "Bazı balina ve yunus türleri karmaşık sesler taklit edebilir.",
    "Solucanlar, toprağı havalandırıp besin döngüsüne katkı sağlayarak tarım için hayati önem taşır.",
    "Bazı kertenkele türleri, kuyruklarını kopararak yırtıcılardan kaçabilir ve zamanla yeni bir kuyruk büyütebilir.",
    "Panda ayıları günde 12 saate kadar sadece bambu yiyerek geçirebilir.",
    "Bir yusufçuk, dört kanadını birbirinden bağımsız hareket ettirerek havada anında yön değiştirebilir.",
    "Mercan resifleri, okyanus tabanının yalnızca küçük bir kısmını kaplamasına rağmen deniz canlılarının çeyreğine ev sahipliği yapar.",
    "Bazı ağaçlar, tohumlarının yayılması için hayvanların onları yemesine ve dışkılamasına ihtiyaç duyar.",
    "Yarasa gübresi (guano), birçok mağara ekosisteminin temel besin kaynağıdır.",
    "Bir çita, saatte 110 kilometreye kadar hız yapabilir ama bu hızı yalnızca birkaç saniye sürdürebilir.",
    "Bitkiler, kök sistemleri aracılığıyla toprak altındaki su ve mineralleri kilometrelerce öteden taşıyabilir.",
    "Orman yangınları bazı ekosistemler için doğal ve gerekli bir yenilenme sürecidir.",
    "Bir semender, kopan bir uzvunu -bacak, kuyruk, hatta bazı organ dokularını- yeniden büyütebilir.",
    "Goril aileleri, her gece yeni bir yatak yaparak uyur; yataklar dallardan ve yapraklardan örülür.",
    "Bazı böcekler, kendi vücut ısılarını çevrelerinden 10 dereceye kadar farklı tutabilir.",
    "Deniz kaplumbağaları, doğdukları plaja yıllar sonra yumurtlamak için geri dönebilir.",
    "Bir orman ekosisteminde, ölü ağaçlar bile yüzlerce böcek ve mantar türüne yaşam alanı sunar.",
    "Timsahlar, dişlerini yaşamları boyunca defalarca yenileyebilir.",
    "Bazı kuş türleri, göç sırasında yıldızların konumunu kullanarak yön bulur.",
    "Ağustosböcekleri, toprak altında 17 yıla kadar larva olarak yaşayabilir.",
    "Bir orman tabanındaki yosunlar, nemi süngerimsi yapılarıyla tutarak toprak erozyonunu önler.",
    "Bazı balık türleri, cinsiyetlerini yaşamları boyunca değiştirebilir.",
    "Vahşi kurtların ulumaları, sürünün bir arada kalmasını sağlayan iletişim yöntemidir.",
    "Bir orman, aynı anda hem karbon deposu hem de biyoçeşitlilik cenneti olarak işlev görür.",
    "Bazı bitki tohumları, toprakta onlarca yıl uyku halinde kalıp uygun koşullar oluşunca çimlenebilir.",
    "Yunuslar, birbirlerini tanımak için özel ıslık sesleri (imza ıslıkları) kullanır.",
    "Bir orman yangınının ardından ilk büyüyen bitkilere 'öncü türler' denir ve toprağı yeniden zenginleştirirler.",
    "Denizatları, yumurtaları erkek bireyin karnında taşıması ve doğurmasıyla hayvanlar aleminde eşsizdir.",
    "Bazı ağaç kabukları, kimyasal bileşikleri sayesinde doğal böcek kovucu görevi görür.",
    "Bir orman ekosistemindeki toprak, yüzyıllar boyunca birikmiş organik maddeden oluşur.",
    "Kirpiler, tehdit altında hissettiklerinde vücutlarını top haline getirip dikenlerini dışa çevirir.",
    "Bazı kuş türleri, yuvalarını yapmadan önce belirli bitkileri seçerek parazitlerden korunur.",
    "Bir mercan, aslında binlerce küçük deniz canlısının (polip) bir arada yaşadığı koloniden oluşur.",
    "Vahşi filler, ölen aile üyelerinin kemiklerini tanıyıp onlara dokunarak yas tutar gibi davranabilir.",
    "Bazı bitkiler, böcekleri tuzağa düşürüp sindirerek ihtiyaç duydukları azotu topraktan değil avlarından alır.",
    "Bir orman gölgesi, güneşli bir alana göre sıcaklığı 5-10 derece kadar düşürebilir.",
    "Penguenler, kayalardan oluşturdukları taşları eşlerine hediye ederek çiftleşme ritüeli gerçekleştirir.",
    "Bazı ağaçların kökleri, toprak altında komşu ağaçlarla kaynaşarak besin paylaşabilir.",
    "Bir orman ekosisteminde av-avcı dengesi bozulduğunda bütün besin zinciri etkilenir.",
    "Tembel hayvanlar o kadar yavaş hareket eder ki kürklerinde yosun üreyebilir.",
    "Bazı balıklar, elektrik alanları oluşturarak hem avlanır hem de iletişim kurar.",
    "Bir orman tabanındaki mantarlar, ölü organik maddeyi parçalayarak toprağı yeniden besler.",
    "Vahşi atlar, sürü içinde belirli bir hiyerarşiye göre kimin önce su içeceğine karar verir.",
    "Bazı bitki türleri, yaprak şekillerini değiştirerek daha az su kaybetmeye adapte olabilir.",
    "Bir orman, yağmur suyunu depolayıp yavaşça salarak sel riskini azaltan doğal bir sünger görevi görür.",
    "Kutup tilkileri, kışın beyaz, yazın kahverengi kürke geçerek çevreye uyum sağlar.",
    "Bazı böcek türleri, yaprak şeklini taklit ederek yırtıcılardan gizlenir.",
    "Bir orman ekosistemi, farklı yükseklikteki katmanlarıyla her biri ayrı bir yaşam alanı sunar.",
    "Su samurları, uyurken birbirlerinin ellerini tutarak akıntıda sürüklenmemeye çalışır.",
    "Bazı ağaçlar mevsim değişikliklerini algılayıp yaprak dökme zamanını buna göre ayarlar.",
    "Bir orman yangını sonrası toprakta biriken kül, bazı bitki tohumlarının çimlenmesini hızlandırabilir.",
    "Kunduzlar, keskin ön dişleriyle günde onlarca ağacı kemirip devirebilir.",
    "Bazı deniz canlıları, biyolüminesans yani kendi ışığını üretme yeteneğine sahiptir.",
    "Bir orman, kök sistemleriyle toprağı bir arada tutarak heyelan riskini azaltır.",
    "Vahşi köpekbalıkları, milyonlarca yıldır neredeyse hiç değişmeden hayatta kalmış canlı türlerindendir.",
    "Bazı kelebek türleri, kışı geçirmek için binlerce kilometre göç eder.",
    "Bir orman ekosistemindeki her ağaç türü, farklı hayvan ve böcek topluluklarına özel yaşam alanı sunar.",
    "Kirpi balıkları tehdit altında su yutarak vücutlarını normalin birkaç katına şişirebilir.",
    "Bazı bitkiler gece açar ve sadece gece aktif olan tozlayıcı hayvanlar tarafından döllenir.",
    "Bir orman, biyoçeşitliliği sayesinde hastalık ve zararlıların yayılmasını doğal olarak sınırlayabilir.",
    "Vahşi maymunlar, alet kullanarak fındık kırma veya karınca avlama gibi karmaşık davranışlar sergileyebilir.",
    "Bazı balıklar, üreme döneminde binlerce kilometre yüzerek doğdukları nehre geri döner.",
    "Bir orman tabanındaki çürüyen yapraklar, toprağın besin döngüsünün temelini oluşturur.",
    "Kutup ayıları, kokuyu kilometrelerce öteden alarak av bulabilir.",
    "Bazı ağaç türleri, yıldırım çarptığında bile hayatta kalabilecek kalınlıkta kabuk geliştirir.",
    "Bir orman, farklı türlerin birbirine bağımlı yaşadığı karmaşık bir besin ağı oluşturur.",
    "Vahşi tavşanlar, tehlike anında ayaklarını yere vurarak diğerlerini uyarır.",
    "Bazı kuşlar, yuvalarını yaparken kendi tüylerini kullanarak yavrularını yalıtır.",
    "Bir orman ekosisteminde yer alan her tür, doğrudan ya da dolaylı olarak diğer tüm türlerle bağlantılıdır.",
    "Kutup ayısı yavruları, doğduklarında yaklaşık yarım kilogram ağırlığındadır.",
    "Bazı ağaçlar, köklerinden salgıladıkları kimyasallarla çevrelerinde başka bitkilerin büyümesini engelleyebilir.",
    "Bir orman, farklı mevsimlerde farklı renklere bürünerek kendine has bir ekosistem döngüsü sergiler.",
]


def load_state() -> list[int]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                remaining = json.load(f)
            if isinstance(remaining, list) and remaining:
                return remaining
        except (json.JSONDecodeError, OSError):
            pass
    remaining = list(range(len(FACTS)))
    random.shuffle(remaining)
    return remaining


def save_state(remaining: list[int]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(remaining, f)


def commit_state() -> None:
    try:
        subprocess.run(["git", "config", "user.name", "nature-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", STATE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Bilgi döngüsü durumu güncellendi", "--allow-empty"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print("Durum commit edilemedi (kritik değil):", e)


def get_next_fact() -> str:
    remaining = load_state()
    index = remaining.pop()
    save_state(remaining)
    commit_state()
    return FACTS[index]


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


def get_unsplash_image_url(query: str = "forest nature") -> str:
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
    print("Paylaşıldı:", result["post"])


def main() -> None:
    org_id = get_organization_id()
    channel_id = get_twitter_channel_id(org_id)
    text = get_next_fact() + "\n\n" + HASHTAGS
    image_url = get_unsplash_image_url()
    create_post(channel_id, text, image_url)


if __name__ == "__main__":
    main()
