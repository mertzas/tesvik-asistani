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
| ✅ | **IP başına hız sınırı gerçek istemciye göre** | 2026-10-08'e kadar uvicorn yalnızca 127.0.0.1'in vekil başlıklarına güveniyordu; nginx arkasında her ziyaretçi nginx'in IP'sini paylaştı (login 10/dk herkes için ortak sayaç). Artık nginx'e sabit IP (`NGINX_IP`, varsayılan 10.231.57.10, alt ağ `TESVIK_ALT_AG` 10.231.57.0/24) verilir, `TRUSTED_PROXIES` yalnızca ona güvenir; hem uvicorn `--forwarded-allow-ips` hem `app/rate_limit.py` `istemci_ip` aynı değeri okur. Alt ağ sunucudaki başka bir ağla çakışırsa `docker compose up` hata verir: `.env`'de iki değişkeni birlikte değiştirin. Mevcut kurulumda ilk geçiş `docker compose down && up -d` ister. Önüne Cloudflare/yük dengeleyici eklenirse onun aralıkları da `TRUSTED_PROXIES`'e ve nginx `set_real_ip_from`'a eklenmeli. |
| ⚠️ | **Zamanlayıcı çok işçide tek sefer: Linux'ta kanıt bekliyor** | `SCHEDULER_LOCK_FILE` kilidi Linux'ta `fcntl`, Windows'ta `msvcrt` ile (2026-10-13); iki ayrı tanıtıcıyla ikinci alma denemesinin reddedildiği birim test Windows'ta da koşuyor. Linux'ta gerçek `--workers 2` kanıtı alınamadı (Docker/WSL yok): üretimde ilk açılışta zamanlayıcı günlüğünün tek işçide çıktığı doğrulanmalı. |
| ⚠️ | **Docker/nginx yapılandırması canlıda denenmedi** | 2026-10-07 denetiminde nginx `/static/` alias'ı, çakışan güvenlik başlıkları, 60 sn `proxy_read_timeout`, `deploy.sh`'ın dev imajı build etmesi düzeltildi; vekil arkası istemci IP'si (yukarıda) 2026-10-13'te commit edildi. Bu makinede Docker olmadığı için `docker compose up` ile uçtan uca doğrulanmadı. İlk dağıtımda `docker compose -f docker-compose.prod.yml config` ve `/health` ile teyit edin. |
| ⛔ | **KVKK aydınlatma metni yayına hazır değil** | Veri envanteri koddan çıkarıldı ve günceldir (soru anlama/Groq, çağrı hatırlatması, isteğe bağlı Sentry dahil). Ticaret unvanı, adres, VERBİS kaydı, başvuru kanalı, teknik günlük saklama süresi ve Groq aktarımı için KVKK m.9 güvencesi `DOLDURULACAK` — şirket kuruluşu ve hukuk görüşü olmadan doldurulamaz. |
| ⛔ | **Stripe test modunda** | `sk_test_` anahtarlarıyla çalışıyor; canlı anahtar ve webhook imza doğrulaması üretimde teyit edilmeli. |
| ⛔ | **SMTP kimlik doğrulaması geçmiyor** | `.env`'de `smtp.gmail.com:587` tanımlı; 2026-10-13 teşhisi: DNS, bağlantı ve STARTTLS sağlam, oturum açma aşamasında bağlantı kapanıyor. Gmail normal parolayı kabul etmez: iki adımlı doğrulama açıp 16 haneli uygulama şifresini `SMTP_PASSWORD`'a yazın (`SMTP_USER` gönderen adres). Parola sıfırlama, e-posta doğrulama ve çağrı son tarihi hatırlatmaları buna bağlı; hata artık günlüğe türü ve ipucuyla yazılır (`app/email.py`). |
| ⚠️ | **Göç gerekli: `alembic upgrade head`** | Son göç `s6b8d0f2a789` (profil: planlanan yatırım tutarı; öncekiler `r5a7c9e1f678` rıza sağlayıcısı, `q4f6b8d0e567` uygunluk alanları). Yeni kodla açılmadan önce uygulanmazsa profil sorguları SQL hatası verir. |
| ⚠️ | **Veri betikleri üretim veritabanına ayrıca uygulanmalı** | `data/` git'te değil. `scripts/fix_veri_*` turları (son tur41, 2026-10-13: 369 kayıt, 248 aktif, 1 kararsız, 158 çağrı) üretim veritabanında `--dogrula` ve `--uygula` ile sırayla çalıştırılmalı; her betik kendi yedeğini alır. |
| ⚠️ | **Aktif kayıtlarda alan boşlukları** (248 aktif kayıtta) | 40'ında tutar metni, 19'unda başvuru şartı (kontrol listesi dahil) boş; çoğu TÜBİTAK akademik/etkinlik çağrısı ve KGF paketleri (kaynak sayfa tutar ya da şart yayımlamıyor). Başvuru süresi boş kayıt yok. |
| ⚠️ | **Soru anlama (Groq) isteğe bağlı, varsayılan kapalı** | `SORU_ANLAMA=groq` + `GROQ_API_KEY` ile açılır; kuruluş Ayarlar'dan rıza vermedikçe hiçbir soru gönderilmez. Groq konsolunda Zero Data Retention açık (2026-10-13). Ücretsiz katman model başına günde 200.000 token (~180 soru); sınırda yedek model (`SORU_ANLAMA_YEDEK_MODEL`, varsayılan `openai/gpt-oss-20b`), ikisi de doluysa kelime kalıplarıyla devam. Developer katmanına geçiş Groq tarafında şimdilik kapalı. |
| ⚠️ | **Yedekleme** | docker-compose.prod.yml `backup` servisi her 24 saatte `pg_dump` ile `./backups/` altına sıkıştırılmış yedek alır (`BACKUP_RETENTION_DAYS`, varsayılan 30 gün; bütünlük `gunzip -t` ile kontrol edilir). Yedekler sunucu dışına (S3 vb.) kopyalanmıyor ve geri yükleme (`scripts/restore.sh`) hâlâ hiç denenmedi — ilk dağıtımdan sonra bir kez prova edin. |
| ⚠️ | **Hata izleme isteğe bağlı, DSN yok** | `SENTRY_DSN` tanımlanırsa Sentry açılır (`app/hata_izleme.py`; istek gövdesi, çerez, kimlik başlıkları, sorgu dizesi ve IP gönderilmez). AB bölgesi DSN alınmalı ve KVKK metnindeki Sentry maddesi bölgeyle güncellenmeli. |
| ⚠️ | **İKAS: partner hesabı ve gerçek mağaza testi yok** | Webhook'u uygulama kendisi kaydediyor (`saveWebhook`); doğrulama mağazaya özgü HMAC belirteciyle adreste (İKAS imza tanımlamıyor; belirteç `SECRET_KEY`'e bağlı, anahtar değişirse webhook yeniden kaydedilmeli). Partner hesabı, client id/secret ve iki geliştirme mağazasında gerçek API testi bekliyor; şu an mock modunda doğrulandı. |
| ✅ | **Kaynak linkleri, kararsız kayıtlar, CSP, oturum iptali** | Taşınan KGF/TÜBİTAK sayfaları güncellendi; kararsız kayıt 1'e indi (3308 Geçici 12: 2026-2027 uzatması bulunamadı). CSP `script-src 'self'` (`style-src 'unsafe-inline'` bilerek; Tailwind CDN kaldırıldı). Parola sıfırlama ve "tüm oturumları kapat" eski JWT'leri `oturum_surumu` ile geçersiz kılar. Danışman dış modelsiz (~0,3 sn); Anthropic/Google/OpenAI yapılandırmaları reddedilir. |

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
  `LLM_API_KEY` (yalnız dış dil modeli kullanılacaksa) koyun ve task definition'da secret olarak bağlayın —
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
- `SECRET_KEY`, `APP_URL`, (isteğe bağlı) `LLM_API_KEY`, Stripe anahtarlarını secret olarak girin
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
- `WARNING app.rag` satırları — dış model çağrısı başarısız ya da yanıt dayanak denetiminden geçmeyip yerel danışmana
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
