"""Publish one carefully sourced nature fact to a LinkedIn member or Page."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path
import requests

API_VERSION = (os.getenv("LINKEDIN_VERSION") or "202610").strip()
API_BASE = "https://api.linkedin.com"
FACTS_PATH = Path(__file__).with_name("nature_facts.txt")

def load_facts(path: Path = FACTS_PATH) -> list[str]:
    facts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        _category, separator, fact = line.partition("|")
        fact = (fact if separator else line).strip()
        if len(fact) >= 30:
            facts.append(fact)
    if not facts:
        raise RuntimeError("nature_facts.txt içinde yayınlanabilir bilgi bulunamadı.")
    return facts

def select_daily_fact(facts: list[str], day: date | None = None) -> str:
    if not facts:
        raise ValueError("facts listesi boş.")
    day = day or date.today()
    return facts[day.toordinal() % len(facts)]

def format_linkedin_post(fact: str) -> str:
    fact = " ".join(fact.split()).strip()
    if not fact:
        raise ValueError("LinkedIn gönderisi için bilgi boş.")
    return (
        f"🌿 A nature fact worth pausing for:\n\n{fact}\n\n"
        "The natural world is full of interconnected systems. "
        "Learning one small detail can change how we see the environment around us.\n\n"
        "What nature fact has surprised you recently?\n\n"
        "#Nature #Science #Environment"
    )[:2900]

def build_post_payload(author_urn: str, commentary: str) -> dict:
    return {
        "author": author_urn, "commentary": commentary, "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False,
    }

def linkedin_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}", "Linkedin-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json",
    }

def resolve_author(token: str) -> str:
    configured = (os.getenv("LINKEDIN_AUTHOR_URN") or "").strip()
    if configured:
        if not configured.startswith(("urn:li:person:", "urn:li:organization:")):
            raise RuntimeError("LINKEDIN_AUTHOR_URN geçerli bir person veya organization URN olmalı.")
        return configured
    response = requests.get(f"{API_BASE}/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if response.status_code != 200:
        raise RuntimeError(f"LinkedIn kimlik doğrulaması başarısız ({response.status_code}); token ve openid/profile izinlerini kontrol edin.")
    subject = (response.json().get("sub") or "").strip()
    if not subject:
        raise RuntimeError("LinkedIn userinfo yanıtında üye kimliği (sub) bulunamadı.")
    return f"urn:li:person:{subject}"

def publish_post(commentary: str, dry_run: bool = False) -> str | None:
    token = (os.getenv("LINKEDIN_ACCESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN GitHub Actions secret eksik.")
    author = resolve_author(token)
    print(f"LinkedIn kimliği doğrulandı. Yazar türü: {'organization' if ':organization:' in author else 'member'}")
    if dry_run:
        print("DRY RUN: LinkedIn gönderisi oluşturulmadı.")
        return None
    response = requests.post(f"{API_BASE}/rest/posts",
        headers=linkedin_headers(token), json=build_post_payload(author, commentary), timeout=30)
    if response.status_code not in (200, 201):
        detail = response.text[:800]
        hint = ""
        if response.status_code == 401:
            hint = " Token süresi dolmuş veya geçersiz."
        elif response.status_code == 403:
            hint = " w_member_social izni veya şirket sayfası için w_organization_social/yönetici rolü eksik olabilir."
        elif response.status_code == 426:
            hint = " LinkedIn API sürümü geçersiz veya kullanımdan kalkmış."
        raise RuntimeError(f"LinkedIn gönderisi başarısız ({response.status_code}): {detail}{hint}")
    post_id = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
    if not post_id:
        try:
            post_id = (response.json() or {}).get("id")
        except ValueError:
            post_id = None
    if not post_id:
        raise RuntimeError("LinkedIn 2xx yanıt verdi ancak gönderi kimliği dönmedi; yayın sonucu doğrulanamadı.")
    print(f"LINKEDIN_PUBLISHED id={post_id}")
    return post_id

def main() -> None:
    dry_run = (os.getenv("DRY_RUN") or "").strip().lower() in ("1", "true", "yes")
    post = format_linkedin_post(select_daily_fact(load_facts()))
    print(f"LinkedIn gönderisi hazır ({len(post)} karakter).")
    publish_post(post, dry_run=dry_run)

if __name__ == "__main__":
    main()
