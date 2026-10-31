# X Follow Manager kurulumu

Bu araç yalnızca resmî X API v2 uç noktalarını kullanır. Eski Selenium/çerez oturumu kaldırılmıştır.

## Gerekli erişim

X Developer hesabında OAuth 2.0 User Context yapılandır. Uygulamanın izinleri:
- `users.read`
- `follows.read`
- `follows.write`
- Gerekliyse `offline.access`

GitHub Actions Secrets:
- `X_USER_ACCESS_TOKEN`: kullanıcı bağlamlı OAuth 2.0 access token
- `X_USER_ID`: hesabın sayısal kullanıcı ID'si
- `ENABLE_X_AUTO_FOLLOW`: önce `false`; testlerden sonra açıkça `true`

GitHub Actions Variables:
- `X_TARGET_USER_IDS`: takip edilmesine izin verdiğin sayısal kullanıcı ID'leri (virgülle ayrılmış)
- `X_FOLLOW_MIN_FOLLOWERS`: yeni takip için minimum takipçi sayısı (varsayılan 1000)
- `X_CLEANUP_NONFOLLOWERS`: `true` ise seni takip etmeyen ve takipçi sayısı 1000'in altında olan mevcut takipleri temizleme planına alır
- `X_DAILY_ACTION_CAP`: günlük birleşik işlem limiti; kod bunu en fazla 50 ile sınırlar (varsayılan 10)

## Çalıştırma

Actions > X Follow Manager > Run workflow:
- `dry-run`: yalnızca planı ve adayları loglar, işlem yapmaz.
- `apply`: gerçek takip/takipten çıkma işlemi yapar. Bunun için gerekli secret'lar ve API erişimi gerekir.

Zamanlanmış günlük çalışma güvenlik amacıyla her zaman dry-run modundadır. Gerçek otomatik işlem için önce izinleri, hedef listesini ve deneme logunu kontrol et.

## Önemli sınırlar

- X API erişimi ve endpoint izinleri hesabın Developer planına göre değişebilir; 401/403/429 durumunda araç durur.
- 50 günlük işlem bir güvenli/ban yememe garantisi değildir. Bu sadece yazılımın koyduğu üst sınırdır.
- Araç yalnızca açıkça verdiğin hedef ID'lerini takip eder; rastgele kullanıcı taramaz.
- Temizlik, kendi takip listen ile kendi takipçilerini karşılaştırır; yalnızca karşılıklı takip etmeyen ve takipçi sayısı 1000'in altında olan hesapları aday yapar.
- API erişimi bulunmayan hesaplarda tarayıcı çerezi, parola veya özel web uç noktasıyla işlem yapılmaz.
