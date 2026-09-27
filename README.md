# Doğa/Orman Bilgi Botu — Buffer sürümü (tamamen ücretsiz)

Bu sürüm X'in ücretli developer API'sini kullanmıyor. Buffer, X'e gönderim
maliyetini kendi üstleniyor; sen sadece X hesabını Buffer'a bağlıyorsun.

## 1. Buffer hesabı aç ve X'i bağla
1. buffer.com → ücretsiz hesap aç
2. Dashboard'da **"Connect a channel"** → **X (Twitter)** seç → X hesabınla giriş yapıp izin ver
   (X developer portalına, App'e, karta hiç gerek yok — normal X girişi yeterli)

## 2. Buffer API key al
1. Giriş yapmışken şu adrese git: **publish.buffer.com/settings/api**
2. **"Create personal access token"** (veya benzeri) ile bir key oluştur, kopyala

## 3. Unsplash key al (daha önce aldıysan atla)
- unsplash.com/developers → New Application → Access Key (ücretsiz)

## 4. Yerelde test et (opsiyonel)
```bash
pip install -r requirements.txt
cp .env.example .env   # değerleri doldur
export $(cat .env | xargs)
python twitter_nature_bot.py
```
Script otomatik olarak Buffer hesabındaki organizasyonu ve bağlı X kanalını
bulur — kanal ID'sini elle girmene gerek yok.

## 5. Otomatik/günlük çalıştırma (GitHub Actions — ücretsiz)
1. Bu dosyaları GitHub reponuza yükle (üzerine yaz)
2. `.github_workflows_template/nature_bot.yml` dosyasını
   `.github/workflows/nature_bot.yml` yoluna taşı
3. Repo → Settings → Secrets and variables → Actions → şu 2 secret'ı ekle:
   `BUFFER_API_KEY`, `UNSPLASH_ACCESS_KEY`
   (Eski `TWITTER_*` secret'ları artık kullanılmıyor, silebilirsin)
4. Actions sekmesinden "Run workflow" ile elle test et

Bundan sonra her gün otomatik çalışır — Buffer kuyruğa ekler, X'e otomatik
gönderir, hiçbir maliyet veya bakım gerekmez.

## Notlar
- Bilgi havuzunu (`FACTS` listesi, twitter_nature_bot.py içinde) istediğin
  kadar genişletebilirsin.
- Buffer ücretsiz planda API kişisel key ile açık; kanal bağlıysa ekstra
  ayar gerekmez.
