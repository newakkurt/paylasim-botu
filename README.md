# Doğa / Sosyal Medya Otomasyon Botları

Bu depo; doğa içerikleri üretimi, Buffer üzerinden X paylaşımı, İstanbul hava durumu, Telegram kontrol paneli ve LinkedIn / YouTube yayın akışlarını bir araya getirir.

## Güncel mimari
- **GitHub Actions:** Günlük otomatik yayınların tek zamanlama kaynağıdır.
- **Render:** Telegram komut kontrol panelini çalıştırır. ENABLE_DAILY_SCHEDULER=0 olmalıdır.
- **Buffer:** Ana doğa gönderilerini X kanalına; hava durumu gönderilerini bağlı X ve Instagram kanallarına yollar.
- **LinkedIn:** nature_facts.txt içindeki doğa bilgilerini profesyonel metin olarak günlük üye veya yetkili şirket sayfası adına yayımlar.
- **YouTube:** Pexels'ten dikey, 3 dakikadan kısa klip seçer ve YouTube Data API v3 ile Shorts olarak yükler.
- **Telegram:** Komutlar, çalışma bildirimleri, günlük etkileşim önerileri ve Pexels video gönderileri.

## Otomatik yayın saatleri (Europe/Istanbul)
| Saat | İş | Hedef |
|---|---|---|
| 07:00 | İstanbul hava durumu | Buffer: X + bağlı Instagram |
| 09:00 | Etkileşim önerileri | Telegram |
| 10:00 | Günlük doğa bilgisi | LinkedIn |
| 11:00, 14:00 | Doğa bilgisi + medya | Buffer: X |
| 16:00, 21:00 | Pexels doğa videosu | Telegram |
| 18:00 | Dikey doğa videosu | YouTube Shorts |

## YouTube kurulumu
Google Cloud Console'da proje oluşturun, YouTube Data API v3'ü etkinleştirin ve OAuth consent screen'i yapılandırın. OAuth Client ID (Desktop app) oluşturun. Sadece https://www.googleapis.com/auth/youtube.upload kapsamı ile offline refresh token üretin.
GitHub Actions secrets:
- YOUTUBE_CLIENT_ID
- YOUTUBE_CLIENT_SECRET
- YOUTUBE_REFRESH_TOKEN
- PEXELS_API_KEY (mevcutsa tekrar eklemeyin)
Refresh token'ı sohbete veya repoya yazmayın. Zamanlanmış yüklemeler varsayılan olarak public olur.

## LinkedIn kurulumu
LinkedIn Developer Portal'da uygulama oluşturun ve Share on LinkedIn ürününü etkinleştirerek w_member_social iznini alın. OAuth access token üretin.
GitHub Actions secrets:
- LINKEDIN_ACCESS_TOKEN
- LINKEDIN_AUTHOR_URN (opsiyonel; üye kimliği userinfo üzerinden otomatik alınır. Şirket sayfası için urn:li:organization:... biçiminde girin.)
Şirket sayfası için ayrıca w_organization_social ve uygun sayfa rolü gerekir. LinkedIn token'ları süreli olduğundan süre dolduğunda yenilenmelidir.

## Güvenli test
Yeni workflow'ların Run workflow seçeneği varsayılan olarak dry_run=true çalışır: OAuth/kanal kimliği ve içerik/video hazırlığı kontrol edilir, gerçek yayın yapılmaz. Gerçek gönderim için secret'lar tanımlandıktan sonra manuel çalıştırmada dry_run=false seçin. Zamanlanmış günlük çalıştırmalar gerçek yayın modundadır.

## Platform kapsamı
- **X:** Ana doğa gönderileri Buffer üzerinden zamanlanır.
- **Instagram:** Hava durumu botu bağlı Instagram kanalına Buffer üzerinden gönderi oluşturmayı dener; yayın durumu ayrıca doğrulanmalıdır.
- **LinkedIn:** linkedin_bot.py Posts API /rest/posts üzerinden organik gönderi yayımlar.
- **YouTube:** youtube_bot.py OAuth refresh token ile kanalı doğrular ve dikey klibi videos.insert ile yükler.
- **Telegram:** Kontrol paneli, bildirimler, etkileşim önerileri ve video gönderileri.

## Diğer GitHub Actions secrets
- BUFFER_API_KEY
- GEMINI_API_KEY
- GROQ_API_KEY
- OPENROUTER_API_KEY (opsiyonel)
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- UNSPLASH_ACCESS_KEY
- PEXELS_API_KEY

## Render ayarı
- Repository: newakkurt/paylasim-botu
- Start command: python telegram_control.py
- ENABLE_DAILY_SCHEDULER=0 — günlük işler Actions'ta çalışır.

## Güvenlik
- Token ve API anahtarları yalnızca GitHub Secrets / Render Environment içinde tutulur.
- Otomatik beğeni, takip veya yorum yapılmaz.
- workflow_dispatch varsayılanı dry-run'dır; yanlışlıkla deneme paylaşımı yapılmasını engeller.

## Yerel test
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -s tests -v
