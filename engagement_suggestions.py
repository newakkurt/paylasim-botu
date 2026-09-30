"""
Günlük Etkileşim Önerisi Botu - tamamen manuel/güvenli
----------------------------------------------------------
Hiçbir otomatik takip/yorum İŞLEMİ yapmaz. Sadece Telegram'a o günün
önerilen hesap listesini ve örnek yorum şablonlarını gönderir. Takip etme,
yorum yazma işlemini SEN elinle, kendi X hesabından yaparsın - bu yüzden
hiçbir bot/spam tespiti riski taşımaz.
"""

import os
import random

import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

DAILY_ACCOUNT_COUNT = 27

INTERNATIONAL_ACCOUNTS = [
    "NatGeo", "NatGeoWild", "NatGeoAnimals", "WWF", "Conservation_org",
    "Oceana", "BBCEarth", "Discovery", "sharkweek", "EarthDotCom",
    "NASAEarth", "NOAA", "WCS", "IUCN", "PlanetEarth",
    "Only_One", "greenpeace", "sierraclub", "audubonsociety", "janegoodallinst",
]

TURKISH_ACCOUNTS = [
    "dogadernegi", "WWFTurkiye", "TEMA_Vakfi", "dkm_org", "kuzeydoga",
    "tabiat_dernegi", "yesilist", "cevreseferberligi", "dogakorumamerkezi", "denizyasami",
    "ekolojibirligi", "yabandoga", "ormancivakfi", "tabiatvedoga", "gezginkusdernegi",
    "kuskoruma", "sudernegi", "denizcocuklari", "cevredostlari", "nlpsever",
]

ALL_ACCOUNTS = INTERNATIONAL_ACCOUNTS + TURKISH_ACCOUNTS

COMMENT_TEMPLATES = [
    "Bu paylaşım gerçekten çok değerli, doğayı korumak hepimizin sorumluluğu 🌿",
    "Harika bir farkındalık çalışması, teşekkürler bu içerik için 🙏",
    "Bunu görmek güzel, doğa böyle küçük adımlarla korunuyor 🌍",
    "Çok etkileyici bir kare/bilgi, paylaşım için teşekkürler ✨",
    "Bu tür içerikler daha çok insana ulaşmalı, keşke herkes görse 🌳",
    "Gerçekten ilham verici, bu konudaki çalışmalarınızı takip etmek güzel 💚",
    "Doğaya bu kadar emek verdiğiniz için teşekkürler 🦋",
    "Bu bilgiyi bilmiyordum, çok teşekkürler paylaştığınız için 🌊",
]


def send_message(text: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=10,
    )


def build_message() -> str:
    todays_accounts = random.sample(ALL_ACCOUNTS, min(DAILY_ACCOUNT_COUNT, len(ALL_ACCOUNTS)))
    todays_comments = random.sample(COMMENT_TEMPLATES, 4)

    lines = ["🌱 Bugünün Etkileşim Listesi\n"]
    lines.append(f"Aşağıdaki {len(todays_accounts)} hesabı ziyaret et, güncel bir paylaşımlarına "
                 "göz at ve uygun bir yorumla etkileşime geç:\n")

    for handle in todays_accounts:
        lines.append(f"• https://x.com/{handle}")

    lines.append("\n💬 Örnek yorumlar (istediğini uyarlayarak kullan):\n")
    for comment in todays_comments:
        lines.append(f"— {comment}")

    lines.append(
        "\n⚠️ Hatırlatma: Bunları SEN elinle, kendi hesabından yapmalısın. "
        "Otomatik takip/yorum X tarafından tespit edilip hesabı riske atar."
    )

    return "\n".join(lines)


def main() -> None:
    message = build_message()
    send_message(message)
    print("Günlük etkileşim önerisi gönderildi.")


if __name__ == "__main__":
    main()