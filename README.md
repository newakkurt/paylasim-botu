# Doğa / Sosyal Medya Otomasyon Botları

Bu depo; doğa içerikleri üretimi, Buffer üzerinden X paylaşımı, İstanbul hava durumu, Telegram video gönderimi ve Telegram kontrol panelini bir araya getirir.

## Güncel mimari

- **GitHub Actions:** Tek otomatik zamanlama kaynağıdır. Böylece Render ve Actions aynı içeriği aynı saatte iki kez paylaşmaz.
- **Render:** Telegram komutlarını dinleyen kontrol panelini çalıştırır. Render ortamında `ENABLE_DAILY_SCHEDULER=0` olmalıdır; günlük zamanlamayı Actions yürütür.
- **Buffer:** Ana doğa gönderilerini X kanalına; hava durumu gönderilerini bağlı X ve Instagram kanallarına yollar.
- **Telegram:** Komutlar, çalışma bildirimleri, günlük etkileşim önerileri ve Pexels videoları.
- **Gemini → Groq → isteğe bağlı OpenRouter:** İçerik üretimi için yedekli model zinciri. Sağlayıcı kotası ve kullanılabilirliği garanti edilmez.

## Otomatik yayın saatleri

Saatler Türkiye / Europe-Istanbul saatidir. GitHub cron saatleri UTC olarak tanımlanır.

| Saat | İş | Hedef |
|---|---|---|
| 07:00 | İstanbul hava durumu | Buffer: X + bağlı Instagram |
| 09:00 | Günlük etkileşim önerileri | Telegram |
| 11:00 | Doğa bilgisi + medya | Buffer: X |
| 14:00 | Doğa bilgisi + medya | Buffer: X |
| 16:00 | Pexels doğa videosu | Telegram |
| 21:00 | Pexels doğa videosu | Telegram |

Pazar 20:00 haftalık raporu Telegram kontrol servisi gönderir.

## Telegram komutları

- `/paylas` — Doğa bilgisi üretir ve Buffer üzerinden X'e zamanlar.
- `/hava` — İstanbul hava durumu gönderisini Buffer'a ekler.
- `/video` — Pexels videosunu Telegram'a gönderir.
- `/etkilesim` — Elle yapılacak güvenli etkileşim önerileri gönderir.
- `/durum`, `/rapor`, `/hatalar`, `/yardim`.

## Platform kapsamı — mevcut kodun doğrulanmış davranışı

- **X:** Ana doğa gönderileri Buffer üzerinden otomatik zamanlanır.
- **Instagram:** Hava durumu botu bağlı Instagram kanalına gönderi yapar. Ana doğa içeriği için Instagram metni Telegram'da taslak olarak üretilir; otomatik yayın değildir.
- **LinkedIn:** Ana doğa içeriği için LinkedIn metni Telegram'da taslak olarak üretilir; otomatik yayın değildir.
- **Telegram:** Kontrol paneli, bildirimler, etkileşim önerileri ve video gönderileri.
- **YouTube:** Bu depoda şu anda YouTube OAuth veya video yükleme entegrasyonu bulunmuyor.

## Gerekli GitHub Actions secrets

- `BUFFER_API_KEY`
- `BUFFER_CHANNEL_ID` (opsiyonel; boşsa bağlı X kanalı otomatik aranır)
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY` (opsiyonel)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `UNSPLASH_ACCESS_KEY`
- `PEXELS_API_KEY`

İsteğe bağlı GitHub Actions variables:

- `GEMINI_MODEL` (varsayılan: `gemini-3.8-flash`)
- `GROQ_MODELS` (varsayılan: `openai/gpt-oss-120b,openai/gpt-oss-20b`)
- `OPENROUTER_MODEL`

X API otomatik yanıt özelliği varsayılan olarak kapalıdır; ücretli X API anahtarları olmadan çalışması beklenmez. Telegram üzerinden manuel cevap önerisi kullanılabilir.

## Render ayarı

Render web service:
- Repository: `newakkurt/paylasim-botu`
- Start command: `python telegram_control.py`
- Gerekli env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `ENABLE_DAILY_SCHEDULER=0` — günlük işler GitHub Actions'ta çalıştığı için çift paylaşımı önler.

Render ücretsiz servisleri uykuya geçebilir; bu nedenle ücretsiz planda Telegram komutlarına 7/24 kesintisiz erişim garantisi yoktur.

## Güvenlik ve çalışma ilkeleri

- API anahtarlarını GitHub Secrets / Render Environment üzerinden saklayın; kaynak koda yazmayın.
- X takip yöneticisi varsayılan olarak dry-run çalışır. Gerçek takip/çıkarma yalnızca açık opt-in ve allow-list ile yapılmalıdır.
- Otomatik beğeni ve yorum yapılmaz; etkileşim önerileri kullanıcıya bırakılır.
- Başarısız model veya API çağrısında gönderi atlanabilir. Bu, doğrulanmamış içeriği otomatik yayımlamaktan daha güvenlidir.

## Yerel test

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -s tests -v
```
