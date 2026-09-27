# Doğa/Orman Bilgi Botu — Kurulum

## 1. API anahtarlarını al
- **Anthropic**: console.anthropic.com → API key
- **X (Twitter)**: developer.x.com → yeni App oluştur → App permissions'ı **Read and Write** yap → Keys and tokens'tan 4 değeri al (API Key/Secret, Access Token/Secret). Ücretsiz katman post atmaya yetmiyor, en az **Basic** paket ($100/ay) gerekiyor.
- **Unsplash**: unsplash.com/developers → yeni app → Access Key
- **OpenAI**: platform.openai.com → API key (görsel üretimi ücretli, ~görsel başına birkaç cent)

## 2. Yerelde test et
```bash
pip install -r requirements.txt
cp .env.example .env   # değerleri doldur
export $(cat .env | xargs)   # ya da python-dotenv kullan
python twitter_nature_bot.py
```

## 3. Otomatik/günlük çalıştırma (GitHub Actions — ücretsiz)
1. Bu dosyaları bir GitHub repo'suna at (private repo olabilir)
2. `.github_workflows_template/nature_bot.yml` dosyasını `.github/workflows/nature_bot.yml` yoluna taşı
3. Repo → Settings → Secrets and variables → Actions → her API anahtarını "New repository secret" olarak ekle (isimler .env.example ile birebir aynı olmalı)
4. Actions sekmesinden "Run workflow" ile elle test et, sorun yoksa her gün 09:00 UTC'de kendiliğinden çalışır

## Notlar
- `IMAGE_MODE=mixed` her paylaşımda %50 Unsplash, %50 AI-üretim arasında rastgele seçim yapar. İstersen `.env`'de `stock` ya da `ai` olarak sabitleyebilirsin.
- Unsplash kullanımı ücretsiz ama demo App'lerde saatlik istek limiti var (50/saat) — günde 1 paylaşım için sorun değil.
- Twitter/X App'in "Read and Write" izni olmazsa `media_upload` veya `create_tweet` 403 hatası verir — en sık karşılaşılan sorun bu.
