# Teşvik Asistanı

KOBİ'lere, çiftçilere ve e-ticaret işletmelerine devlet teşviklerini eşleştiren
ve bütçe önerisi üreten SaaS uygulaması. Veri kaynakları: KOSGEB, TÜBİTAK, KGF,
Tarım Bakanlığı, Hazine/Ticaret Bakanlığı, TÜİK, TCMB EVDS ve Hal Kayıt Sistemi.

- **Teşvik eşleştirme:** işletme profiline (sektör, il, ciro, çalışan sayısı,
  ürün) göre puanlanmış program listesi
- **Bütçe önerisi:** TCMB sektör bilançolarına ve TÜİK enflasyonuna dayanan
  stok maliyeti / reklam bütçesi aralıkları
- **AI danışman:** Claude API ile, yalnızca veritabanındaki kayıtlara dayanan
  (uydurma yapmayan) yanıtlar; API anahtarı yoksa liste formatına düşer
- **Veri tazeliği göstergesi:** her kaynağın ne zaman güncellendiği panelde
  görünür
- **İKAS entegrasyonu:** OAuth2 + Admin GraphQL ile sipariş verisinden profil
  çıkarımı (şu an mock modda, bkz. [İKAS](#i̇kas-entegrasyonu))

---

## Kurulum (yerel geliştirme)

Gereken: **Python 3.11+**. Veritabanı olarak SQLite kullanılır, ayrıca bir
sunucu kurmanız **gerekmez**.

> Daha önceki README/SETUP/QUICKSTART dosyaları PostgreSQL kurup
> `createdb tesvik_saas` demenizi söylüyordu. Bu yanlıştı: `psycopg2`
> varsayılan olarak kurulmuyor ve uygulama SQLite ile çalışıyor. PostgreSQL
> yalnızca üretim için gerekli, bkz. [DEPLOYMENT.md](DEPLOYMENT.md).

```bash
python -m venv venv
venv\Scripts\activate          # Windows;  Linux/macOS: source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Ortam değişkenlerini hazırlayın:

```bash
copy .env.example .env
```

`.env` içinde en az `SECRET_KEY` doldurulmalı. `ANTHROPIC_API_KEY` boş
bırakılırsa AI danışman devre dışı kalır, uygulamanın kalanı çalışır.

Veritabanı şemasını kurun:

```bash
alembic upgrade head
```

Veritabanı zaten doluysa baştan yaratmayın, yalnızca damgalayın:
`alembic stamp head`. Ayrıntı ve tuzaklar: [migrations/README.md](migrations/README.md).

İlk veriyi toplayın (ilk çalıştırmada birkaç dakika sürer):

```bash
python -m scripts.tum_verileri_guncelle
```

Sunucuyu başlatın:

```bash
uvicorn app.main:app --reload --port 8000
```

- Uygulama: http://localhost:8000
- Panel: http://localhost:8000/dashboard
- API dokümanı (otomatik): http://localhost:8000/docs
- Veri durumu: http://localhost:8000/api/veri-durumu

---

## Veri tazeleme

Öneriler dış kaynaklardan gelen veriye dayanıyor; bayat veri sessizce yanlış
sonuç üretir. Tüm kaynakları tazelemek için:

```bash
python -m scripts.tum_verileri_guncelle
```

Tek kaynak için: `--sadece makro,hal`. Kaynak listesi: `--liste`.
Herhangi bir kaynak başarısız olursa çıkış kodu `1` olur.

Kaynakların hangi sıklıkta yayınlandığı ve ne zaman "bayat" sayıldığı
[app/veri_tazeligi.py](app/veri_tazeligi.py) içinde kaynak kaynak
tanımlanmıştır (hal fiyatları her iş günü, TÜİK enflasyonu ayda bir, TCMB
sektör bilançoları yılda bir yayınlanır — hepsine aynı eşiği uygulamak
yanıltıcı olurdu).

### Haftalık otomatik tazeleme (Windows)

`run_scrapers.bat` tüm kaynakları tazeler ve sonucu `data/scraper_log.txt`
dosyasına yazar. Zamanlanmış görev olarak kaydetmek için:

```bash
schtasks /create /tn TesvikAsistaniScraper /tr "%CD%\run_scrapers.bat" /sc weekly /d MON /st 03:00
```

**Projeyi başka bir klasöre taşırsanız görevi yeni yola yönlendirin** —
görev `.bat` dosyasının yolunu saklar ve eski yol kaybolunca sessizce
çalışmaz olur:

```bash
schtasks /change /tn TesvikAsistaniScraper /tr "<yeni yol>\run_scrapers.bat"
```

`app/scheduler.py` içindeki APScheduler işleri de aynı kaynakları tazeler ama
**yalnızca sunucu ayaktayken** tetiklenir; 7/24 çalışmayan bir makinede tek
başına yeterli değildir.

---

## Testler

```bash
pytest
```

176 test; `tests/conftest.py` her test için bellek içi SQLite kurup düşürür,
yerel veritabanınıza dokunmaz.

Şema ile modellerin uyumunu kontrol etmek için:

```bash
alembic check
```

---

## Proje yapısı

```
app/
  main.py                 FastAPI uygulaması ve HTTP endpoint'leri
  models.py               SQLAlchemy modelleri (Organization, User, Tesvik, ...)
  models_cilek.py         Çilek paneli modelleri (aynı Base'i paylaşır)
  auth.py                 JWT kimlik doğrulama (PyJWT)
  matching.py             Teşvik eşleştirme ve puanlama motoru
  budget.py               Bütçe önerisi hesaplaması
  rag.py                  Claude API ile AI danışman (+ liste formatına düşme)
  veri_tazeligi.py        Veri kaynaklarının yaş/durum raporu
  rate_limit.py           Kayan pencere hız sınırlama
  logging_setup.py        Merkezi günlükleme yapılandırması
  billing.py              Stripe abonelik akışı
  scheduler.py            APScheduler zamanlanmış tazeleme işleri
  ikas_*.py               İKAS OAuth + GraphQL entegrasyonu
  scrapers/               Kurum ve fiyat veri toplayıcıları
  static/                 Panel ve açılış sayfası (statik HTML/JS)
scripts/
  tum_verileri_guncelle.py   Tüm kaynakları tazeleyen tek giriş noktası
  seed_*.py / backfill_*.py  Bir defalık veri doldurma script'leri
migrations/               Alembic göçleri (bkz. migrations/README.md)
tests/                    pytest
docs/                     API, mimari ve pazarlama dokümanları
```

---

## Önemli endpoint'ler

| Endpoint | Açıklama |
|---|---|
| `POST /api/auth/signup`, `POST /api/auth/login` | Kayıt / giriş, JWT döner |
| `POST /api/sor` | AI danışman sorusu |
| `GET /api/eslesme` | Profil bazlı teşvik eşleştirme |
| `GET /api/butce-onerisi` | Bütçe önerisi (PRO) |
| `GET`/`PUT` `/api/profil` | Finansal profil |
| `GET /api/veri-durumu` | Veri kaynaklarının tazeliği (kimlik doğrulaması gerekmez) |
| `GET /api/nace/ara?q=sera` | 9903 sayılı Karar EK-3 listesinde arama (kimlik doğrulaması gerekmez) |
| `GET /api/nace/uygunluk?kod=01.19.99&il=Konya&olcek=8` | NACE kodu teşvik kapsamında mı, ölçeğiniz asgari şartı tutuyor mu |
| `GET /health` | Sağlık kontrolü + veri durumu |

Tam liste ve istek/yanıt gövdeleri: [docs/API.md](docs/API.md) ve çalışan
sunucuda `/docs`.

Hız sınırları organizasyon bazlıdır ve [app/rate_limit.py](app/rate_limit.py)
içinde tanımlıdır. Sayaçlar süreç içi tutulur; çok işçili dağıtımda Redis'e
taşınması gerekir.

---

## İKAS entegrasyonu

OAuth2 Authorization Code akışı ve Admin GraphQL API v2 uygulanmış durumda,
ancak **şu an mock modda çalışıyor**: gerçek `client_id`/`client_secret`
henüz üretilmedi. Üretmek için İKAS CLI'ya giriş yapılması gerekiyor:

```bash
npm i -g ikas
ikas auth login
ikas app init
```

`ikas app init` OAuth kimlik bilgilerini üretir ve bir test mağazası verir;
bunlar `.env` dosyasına yazıldığında entegrasyon mock modundan çıkar.

---

## NACE kodları ve 9903 sayılı Karar

Yatırım teşvik sistemi 2025'te değişti: **9903 sayılı "Yatırımlarda Devlet
Yardımları Hakkında Karar"** (Resmî Gazete, 30/05/2025) 2012/3305 sayılı
Karar'ı yürürlükten kaldırdı. Yeni sistem yatırım konularını **NACE Rev.2.1**
kodlarıyla tanımlıyor ve başvuruları Karar'ın **EK-3** listesiyle bu kodlar
üzerinden eşleştiriyor.

[app/nace_9903.py](app/nace_9903.py) o resmî listeyi uygulamaya taşıyor:

- **EK-2 il–bölge eşleşmesi** (81 il, 6 bölge). Asgari şartlar bölgeye göre
  değiştiği için bu eşleşme olmadan hiçbir hüküm verilemez.
- **EK-3 listesinin tamamı** (87 NACE kodu, 11 bölüm) —
  [app/data/ek3_9903.json](app/data/ek3_9903.json), Karar PDF'inden otomatik
  çıkarıldı. Şartlar serbest metin olarak saklanır.
- **Yapılandırılmış asgari eşikler yalnızca tarım (EK-3 bölüm A) için.**
  Diğer bölümlerin şartları asgari sabit yatırım tutarı gibi profilde
  bulunmayan verilere dayandığı için orada sayısal hüküm verilmiyor, yalnızca
  resmî şart metni gösteriliyor. Yapılandırmadığımız bir şartı yorumlamak,
  kullanıcıya yanlış bir "uygunsunuz" güvencesi vermek olurdu.

```bash
curl "http://localhost:8000/api/nace/uygunluk?kod=01.19.99&il=Konya&olcek=8"
# -> yetersiz: Konya 2. bölgede asgari 20 dekar, 12 dekar daha gerekiyor
curl "http://localhost:8000/api/nace/uygunluk?kod=01.19.99&il=Van&olcek=8"
# -> uygun: Van 6. bölgede asgari 5 dekar
```

**Kapsam sınırı:** bu eşikler **yatırım teşvik belgesi** içindir (vergi
indirimi, KDV istisnası, sigorta primi desteği). KOSGEB hibeleri, TÜBİTAK
proje destekleri ve Tarım Bakanlığı'nın dekar/hayvan başı ödemeleri ayrı
programlardır ve bu eşiklere tabi değildir.

Yürürlükten kalkan kayıtları işaretleyen ve yeni programları ekleyen script:

```bash
python -m scripts.mark_9903_yururlukten_kalkanlar            # rapor
python -m scripts.mark_9903_yururlukten_kalkanlar --uygula
```

---

## Mimari

Çok kiracılı (multi-tenant): her `Organization` bir veya daha fazla `User`
içerir, tüm veriler `org_id` ile ayrılır. Planlar: FREE / PRO / BUSINESS
(Stripe ile, şu an test modunda).

Teknoloji: FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite (üretimde PostgreSQL),
APScheduler, Anthropic Claude API, Stripe.

Ayrıntı: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Dağıtım

Docker Compose, AWS EC2 ve yönetilen platform seçenekleri ile üretim öncesi
kontrol listesi: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Dokümanlar

| Dosya | İçerik |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Üretime alma, Docker, kontrol listesi |
| [docs/API.md](docs/API.md) | Endpoint referansı |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Sistem mimarisi |
| [docs/MARKETING.md](docs/MARKETING.md) | Pazara giriş stratejisi |
| [migrations/README.md](migrations/README.md) | Veritabanı göçleri |
