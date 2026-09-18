# Veritabanı Göçleri (Alembic)

Şema artık **kod içinde** sürümleniyor. Ekip büyüdüğü için `Base.metadata.create_all()`
ile "çalışırken tablo yarat" yaklaşımı bırakıldı: o yöntem yeni tablo ekleyebiliyor
ama var olan bir tabloya **sütun ekleyemiyor**, dolayısıyla iki geliştiricinin
veritabanı sessizce farklılaşıyordu.

## Günlük kullanım

Şemayı en güncel hale getir (herkes `git pull` sonrası bunu çalıştırmalı):

```bash
alembic upgrade head
```

Model değiştirdikten sonra yeni göç üret:

```bash
alembic revision --autogenerate -m "kisa aciklama"
```

Üretilen dosyayı **mutlaka aç ve oku** — autogenerate mükemmel değildir:
sütun yeniden adlandırmayı "sil + ekle" olarak görür (veri kaybı!) ve
sunucu tarafı varsayılanlarını kaçırabilir.

Son göçü geri al:

```bash
alembic downgrade -1
```

## Bu kurulumda bilerek yapılmış tercihler

- **`migrations/env.py` hem `app.models` hem `app.models_cilek` import eder.**
  İkisi aynı `Base`'i paylaşıyor. Sadece ilki import edilirse çilek tabloları
  metadata'ya kaydolmaz ve autogenerate onları "fazlalık" sanıp
  `DROP TABLE` üretir. Yeni bir model dosyası eklerseniz env.py'a import edin.

- **Veritabanı adresi `app.models.settings.DATABASE_URL`'den okunur**,
  `os.getenv`'den değil. `.env` dosyasını pydantic-settings okuyor; doğrudan
  `os.getenv` kullanılırsa alembic yanlış veritabanına bağlanır.

- **SQLite'ta batch modu açık.** SQLite `ALTER TABLE`'ı kısıtlı destekler;
  batch modu olmadan sütun silme/tip değiştirme göçleri hata verir.

## Mevcut veritabanı olan bir makinede ilk kurulum

Veritabanınız zaten doluysa baştan yaratmayın, sadece damgalayın:

```bash
alembic stamp head
```

Üretim veritabanı (`data/tesvikler.db`, 174 teşvik / 1354 hal fiyatı)
2026-09-18'de `eafd5ed73993` olarak damgalandı.

## Doğrulama

`eafd5ed73993` (başlangıç şeması) boş bir veritabanında çalıştırıldığında
`create_all()` ile **birebir aynı** şemayı üretiyor: 82/82 nesne, tek SQL
farkı yok. `downgrade base` de tüm tabloları temiz şekilde düşürüyor.
