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
| ⛔ | **Hız sınırlama sayaçları süreç içi** | `app/rate_limit.py` sayaçları RAM'de tutar. `--workers 2` ile her işçi kendi sayacını tutar, gerçek limit iki katına çıkar. Çok işçili dağıtımda Redis'e taşınmalı. |
| ⛔ | **KVKK aydınlatma metni ve veri işleme kaydı yok** | Kişisel ve finansal veri işleniyor. Şirket kurulup VERBİS kaydı yapılmadan yayın hukuken riskli. |
| ⛔ | **Stripe test modunda** | `sk_test_` anahtarlarıyla çalışıyor; canlı anahtar ve webhook imza doğrulaması üretimde teyit edilmeli. |
| ⛔ | **115 teşvik kaydının açık/kapalı durumu doğrulanmamış** (176 kaydın) | `aktif_mi` alanı boş olan kayıtlar için AI danışman "kurumun sayfasından teyit edin" uyarısı basıyor, ama kullanıcı yine kapanmış bir programa yönlenebilir. |
| ⚠️ | **162 kayıtta başvuru şartları eksik** | Eşleşme çalışıyor ama kullanıcı "başvurabilir miyim" sorusunun cevabını kayıttan alamıyor. |
| ⚠️ | **Yük testi hiç yapılmadı** | Eşzamanlı kullanıcı davranışı bilinmiyor. `/api/sor` her çağrıda Claude API'ye gidiyor; gecikme ve maliyet ölçülmeli. |
| ⚠️ | **Yedekleme otomatik değil** | `scripts/backup.sh` ve `restore.sh` var ama zamanlanmış değil ve geri yükleme hiç denenmedi. |
| ⚠️ | **Hata izleme yok** | Günlükler dosyaya/konsola yazılıyor, merkezî bir hata toplayıcı (Sentry vb.) bağlı değil. |

Kapatılmış olanlar (referans): şema sürümleme (Alembic), hız sınırlama,
merkezî günlükleme, veri tazeliği göstergesi, otomatik veri tazeleme,
üretim bağımlılıklarının doğruluğu.

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
