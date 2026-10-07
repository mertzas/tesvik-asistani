# Dağıtım

Bu dosya `DEPLOYMENT.md`, `PRODUCTION_CHECKLIST.md` ve `PRODUCTION_READY.md`
dosyalarının birleştirilmiş hâlidir. Üçü aynı konuyu farklı ve yer yer
çelişkili şekilde anlatıyordu; `PRODUCTION_READY.md` ayrıca **hiç yapılmamış**
yük testi sonuçları ("Apache Bench, 1000 istek") ve var olmayan bir komut
(`uvicorn app.main_prod:app`) içerdiği için kaldırıldı.

Yerel geliştirme kurulumu için [README.md](README.md).

---

## Üretime almadan önce kapatılması gerekenler

Aşağıdakiler **bilinen ve açık** eksikler. Uygulama çalışıyor ama bunlar
kapatılmadan ödeme alan bir servis olarak yayına verilmemeli.

| Durum | Konu | Neden önemli |
|---|---|---|
| ✅ | **Hız sınırlama sayaçları** | `REDIS_URL` doluysa Redis'te (docker-compose.prod.yml `redis` servisi), boşsa süreç içi. Redis'e ulaşılamazsa istek reddedilmez, günlüğe yazılır ve limit işçi başına gevşer. |
| ⚠️ | **Zamanlayıcı çok işçide tek sefer: yalnızca birim testli** | `SCHEDULER_LOCK_FILE` ile `flock` kilidi (`fcntl`) kodda ve birim testte var. Windows'ta `fcntl` yok: iki gerçek süreç de kilidi aldı (2026-10-07 deneyi). Linux'ta gerçek `--workers 2` kanıtı alınamadı (Docker/WSL yok); üretimde ilk açılışta zamanlayıcı günlüğünün tek işçide çıktığı doğrulanmalı. |
| ⚠️ | **Docker/nginx yapılandırması canlıda denenmedi** | 2026-10-07 denetiminde nginx `/static/` alias'ı (kapsayıcıda olmayan dizin → 404), çakışan güvenlik başlıkları, 60 sn `proxy_read_timeout` (SSE yanıtı 35-70 sn), `deploy.sh`'ın dev imajını build edip yalnızca `restart` etmesi düzeltildi; ancak bu makinede Docker olmadığı için `docker compose up` ile uçtan uca doğrulanmadı. İlk dağıtımda `docker compose -f docker-compose.prod.yml config` ve `/health` ile teyit edin. |
| ⛔ | **KVKK aydınlatma metni yayına hazır değil** | Metin yazıldı ve `/kvkk` adresinde yayında; veri envanteri kodun şemasından çıkarıldı ve doğru. Ancak ticaret unvanı, adres, VERBİS kaydı ve başvuru kanalı `DOLDURULACAK` işaretli — şirket kuruluşu tamamlanmadan doldurulamaz ve bu alanlar dolmadan aydınlatma yükümlülüğü karşılanmaz. |
| ⛔ | **Stripe test modunda** | `sk_test_` anahtarlarıyla çalışıyor; canlı anahtar ve webhook imza doğrulaması üretimde teyit edilmeli. |
| ⚠️ | **12 kaydın açık/kapalı durumu kararsız (186 kaydın: 99 aktif, 75 kapalı)** | Kararsızlar arasında çiftçi için kritik KKYP (78), TSS (80) ve Hayvancılık (76) var; danışman bu kayıtlar için "aktifliği teyit edin" diyor. Diğer 9'u akademik/etkinlik çağrıları. Aktiflik kuralı: kurum sayfasında yüksek güvenli ifade yoksa karar verilmez. |
| ⚠️ | **Aktif kayıtlarda alan boşlukları** (99 aktif kayıtta) | 26'sında başvuru şartı, 46'sında tutar metni, 73'ünde başvuru süresi boş; 37 aktif kayıt Denetim 2'de canlı sayfayla karşılaştırılmadı ve 37'sinin ham metni menü kazıması içeriyor (danışman bağlamında ayıklanıyor). Kayıt 7'de görüldüğü gibi kazınmış metin bir dönem geride kalabiliyor. |
| ⚠️ | **Yük/dayanıklılık kısmen ölçüldü; gerçek modelle akış süresi ölçülmedi** | 30 sn × 5 iş parçacığı ve eşzamanlı 5 akış/eşleşme isteği temiz; sahte Claude 500/529/kopma/askıda ve kilitli DB deneyleri yapıldı (`docs/olcum/2026-10-07-denetim2/D_RAPOR.md`). Claude kredisi bitince ilk parça/toplam süre ve maliyet ölçümü yapılamadı; en kötü durumda askıda bağlantı 180 sn bekletir (nginx sınırı 300 sn). |
| ✅ | **Ölü kaynak linkleri** | Denetim 2 / Aşama A'da KGF ve TÜBİTAK'ın taşınan sayfaları bulundu ve güncellendi (46 kayıt yeni URL). Kalan: kayıt 163 güncel limit, kayıt 48 son başvuru tarihi. |
| ⚠️ | **Yedekleme** | docker-compose.prod.yml `backup` servisi her 24 saatte `pg_dump` ile `./backups/` altına sıkıştırılmış yedek alır (`BACKUP_RETENTION_DAYS`, varsayılan 30 gün; bütünlük `gunzip -t` ile kontrol edilir). Yedekler sunucu dışına (S3 vb.) kopyalanmıyor ve geri yükleme (`scripts/restore.sh`) hâlâ hiç denenmedi — ilk dağıtımdan sonra bir kez prova edin. |
| ⛔ | **SMTP tanımlı değil: parola sıfırlama ve e-posta doğrulama postası gitmez** | Akış kodda hazır ve testli (`/api/auth/sifre-unuttum`, `/sifre-sifirla`, `/eposta-dogrula`); `SMTP_SERVER/PORT/USER/PASSWORD` `.env`'de boşsa istekler başarılı döner ama posta gönderilmez, günlüğe uyarı düşer. Yayından önce bir SMTP sağlayıcısı bağlanmalı ve gerçek bir hesapla uçtan uca denenmeli. |
| ⚠️ | **Göç gerekli: `alembic upgrade head`** | Aşama E göçü (`g4b6c8d0e456`) `users.email_dogrulama_zamani` sütununu ve `hesap_belirtecleri` tablosunu ekler. Yeni kodla açılmadan önce uygulanmazsa giriş SQL hatası verir. Kopya DB'de yukarı/aşağı/yukarı denendi. |
| ⚠️ | **CSP `script-src 'unsafe-inline'` içeriyor** | Paneller satır içi `onclick` vb. kullanıyor. Dış script/çerçeve/form hedefi/`<base>` engelli, `connect-src 'self'`; ancak enjekte edilmiş satır içi script'i engellemez. Olay yöneticileri nonce'a taşınınca kaldırılır. Çilek paneli Tailwind'i CDN'den yüklüyor (`cdn.tailwindcss.com`, üretimde önerilmez). |
| ⚠️ | **İKAS webhook imzası yok (İKAS tanımlamıyor)** | İKAS belgesi webhook imzası/secret tanımlamıyor; doğrulama mağazaya özgü HMAC belirteciyle adreste yapılıyor (`GET /api/ikas/durum` → `webhook_url`). Belirteç `SECRET_KEY`'e bağlı: anahtar değişirse webhook yeniden kaydedilmeli. Gövde şeması belgelenmediği için belirteç mağazayı tek başına belirler. Uygulama webhook'u İKAS'ta kendisi kaydetmiyor; mağaza sahibi `store/order/created` kapsamıyla bu adresi elle kaydetmeli. |
| ⚠️ | **Parola sıfırlamada eski JWT'ler iptal edilmez** | JWT 7 gün geçerli ve iptal listesi yok; parola değişince eski oturumlar süre dolana kadar açık kalır. |
| ⚠️ | **Hata izleme yok** | Günlükler dosyaya/konsola yazılıyor, merkezî bir hata toplayıcı (Sentry vb.) bağlı değil. |

Kapatılmış olanlar (referans): şema sürümleme (Alembic), hız sınırlama,
İKAS token'larının şifrelenmesi, yapay zekâ için yurt dışına aktarım
açık rızası (varsayılan kapalı, geri alınabilir),
merkezî günlükleme, veri tazeliği göstergesi, otomatik veri tazeleme,
üretim bağımlılıklarının doğruluğu, destek tutarı hesaplayıcıları (9903 ve 2026 tarım), aktiflik ve kaynak linki doğrulayıcıları.

---

## Seçenek 1: Docker Compose (tek sunucu)

En basit yol. Bir VPS (DigitalOcean, Hetzner, AWS Lightsail) yeterli.
Minimum 2 GB RAM önerilir.

```bash
# 1. Docker ve Compose kurun (Ubuntu 22.04)
curl -fsSL https://get.docker.com | sh

# 2. Depoyu klonlayın
git clone <repo-url> tesvik-asistani
cd tesvik-asistani

# 3. Sırları hazırlayın
cp .env.example .env
```

`.env` içinde **en az** şunlar doldurulmalı — eksikse `docker compose` açıkça
hata verir (sessizce yer tutucu değerle çalışmaz):

```
SECRET_KEY=          # openssl rand -hex 32
POSTGRES_USER=
POSTGRES_PASSWORD=
APP_URL=https://alanadiniz.com
```

```bash
# 4. Ayağa kaldırın (göçler kapsayıcı açılışında uygulanır)
docker compose -f docker-compose.prod.yml up -d --build

# 5. İlk veriyi toplayın
docker compose -f docker-compose.prod.yml exec web python -m scripts.tum_verileri_guncelle

# 6. Doğrulayın
curl http://localhost:8000/health
```

`/health` yanıtı `veri_durumu` alanını da döner; `bayat` veya `veri_yok`
görürseniz veri toplama adımı eksik kalmış demektir.

### SSL

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d alanadiniz.com
# Sertifikaları ./certs altına kopyalayın (nginx.conf /etc/nginx/certs arar)
docker compose -f docker-compose.prod.yml restart nginx
```

### Haftalık veri tazeleme

```bash
crontab -e
# Her pazartesi 03:00
0 3 * * 1 cd /yol/tesvik-asistani && docker compose -f docker-compose.prod.yml exec -T web python -m scripts.tum_verileri_guncelle >> /var/log/tesvik-veri.log 2>&1
```

Komut başarısızlıkta `1` döner, bu yüzden cron hatası fark edilebilir.

---

## Seçenek 2: AWS (ölçeklenebilir)

ECS Fargate + RDS PostgreSQL. Otomatik ölçeklendirme gerekiyorsa bu yol.

```bash
# 1. ECR deposu
aws ecr create-repository --repository-name tesvik-asistani

# 2. Giriş
aws ecr get-login-password --region eu-central-1 \
  | docker login --username AWS --password-stdin <hesap-id>.dkr.ecr.eu-central-1.amazonaws.com

# 3. İmajı derle ve gönder
docker build -f Dockerfile.prod -t tesvik-asistani .
docker tag tesvik-asistani:latest <hesap-id>.dkr.ecr.eu-central-1.amazonaws.com/tesvik-asistani:latest
docker push <hesap-id>.dkr.ecr.eu-central-1.amazonaws.com/tesvik-asistani:latest
```

Sonra:

- **RDS PostgreSQL 15** oluşturun, yalnızca ECS güvenlik grubundan erişime izin verin
- **Secrets Manager**'a `DATABASE_URL`, `SECRET_KEY`, `STRIPE_SECRET_KEY`,
  `ANTHROPIC_API_KEY` koyun ve task definition'da secret olarak bağlayın —
  ortam değişkeni olarak düz metin girmeyin
- Sağlık kontrolü yolu: `/health`
- Veri tazeleme için ayrı bir **scheduled ECS task** (haftalık,
  `python -m scripts.tum_verileri_guncelle`)

Maliyet, tek görev + küçük RDS ile aylık yaklaşık 80-150 USD bandındadır;
kesin tutar bölge ve örnek boyutuna göre değişir, AWS fiyat hesaplayıcısından
teyit edin.

---

## Seçenek 3: Yönetilen platform (Railway / Render / Fly.io)

DevOps yükü istemiyorsanız: `Dockerfile.prod` doğrudan kullanılabilir.

- Yönetilen PostgreSQL ekleyin, `DATABASE_URL`'i bağlayın
- `SECRET_KEY`, `APP_URL`, `ANTHROPIC_API_KEY`, Stripe anahtarlarını secret olarak girin
- Sağlık kontrolü: `/health`
- Veri tazeleme: platformun cron/scheduled job özelliği ile
  `python -m scripts.tum_verileri_guncelle`

Bu yolda dikkat: birçok platform varsayılan olarak birden fazla işçi/örnek
açar. Hız sınırlama sayaçları süreç içi olduğu için **tek örnek** ile
başlayın (yukarıdaki tabloya bakın).

---

## Dağıtım sonrası kontrol

```bash
# Sağlık ve veri durumu
curl https://alanadiniz.com/health

# Veri kaynaklarının tazeliği
curl https://alanadiniz.com/api/veri-durumu

# Şema modellerle uyumlu mu
docker compose -f docker-compose.prod.yml exec web alembic check

# Göç sürümü
docker compose -f docker-compose.prod.yml exec web alembic current
```

Elle doğrulanması gerekenler:

- [ ] Kayıt ve giriş akışı çalışıyor, JWT dönüyor
- [ ] Teşvik eşleştirme sonuç döndürüyor ve puanlar makul
- [ ] Bütçe önerisi PRO hesapta açılıyor, FREE hesapta 403 veriyor
- [ ] AI danışman yanıt veriyor (anahtar yoksa liste formatına düştüğü görülüyor)
- [ ] Stripe checkout ve webhook'u test işlemiyle deneniyor
- [ ] Panel mobil genişlikte bozulmuyor
- [ ] `/api/veri-durumu` rozeti "taze" gösteriyor

---

## Güvenlik notları

Bu dağıtımda bilinçli olarak yapılanlar:

- **PostgreSQL portu dışarıya açılmıyor** (`expose`, `ports` değil). Önceki
  `docker-compose.prod.yml` 5432'yi ana makineye açıyordu.
- **Sırlar dosyada tutulmuyor.** Önceki compose dosyaları
  `SECRET_KEY: your_secret_key_here_change_in_production` gibi yer tutucuları
  depoya işlemiş durumdaydı; biri değiştirmeyi atlarsa üretim herkesin
  bildiği bir imza anahtarıyla çalışırdı. Artık eksik değişken hata veriyor.
- **Kaynak kodu üretimde bind mount edilmiyor.** Önceki hâli `./app`'i
  kapsayıcıya bağlayarak imajı anlamsız kılıyordu.
- **`DATABASE_URL` imaja gömülmüyor.** Önceki `Dockerfile.prod` içinde
  `ENV DATABASE_URL=postgresql://user:password@db:5432/tesvik_db` vardı;
  böyle bir varsayılan, değişken unutulduğunda hatayı gizler.

Ayrıca yapılması gerekenler:

- HTTPS zorunlu, HTTP'den yönlendirme (`nginx.conf`)
- `SECRET_KEY` her ortamda farklı ve en az 32 bayt
- API anahtarları sızdıysa **döndürün** — anahtar iptal edilmeden depodan
  silinmesi yeterli değildir
- Veritabanı yedeği alın ve **geri yüklemeyi bir kez deneyin** (denenmemiş
  yedek, yedek değildir)

---

## Günlükler ve izleme

```bash
# Uygulama günlükleri
docker compose -f docker-compose.prod.yml logs -f web

# Veri tazeleme günlüğü (yerel/Windows)
tail -f data/scraper_log.txt
```

İzlenmesi anlamlı olanlar:

- `/health` yanıtındaki `veri_durumu` — `bayat` olması scraper'ların
  sessizce durduğu anlamına gelir
- `WARNING app.rag` satırları — Claude çağrısı başarısız olup liste
  formatına düşüldüğünde sebebi (kota/anahtar/ağ) burada yazar
- HTTP 429 sayısı — hız sınırına takılan kullanıcılar

---

## Geri alma

```bash
# Bir önceki imaja dön
docker compose -f docker-compose.prod.yml down
git checkout <onceki-commit>
docker compose -f docker-compose.prod.yml up -d --build

# Şema geri alma (son göçü geri al)
docker compose -f docker-compose.prod.yml exec web alembic downgrade -1
```

Şema geri alma veri kaybedebilir; önce yedek alın.
