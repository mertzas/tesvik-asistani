# Denetim 2 / Aşama D — performans ve dayanıklılık (2026-10-07)

## Yöntem
- Üretim DB'sine dokunulmadı: `data/tesvikler.db` geçici kopyaya alındı, uvicorn :8001'de o kopyayla başlatıldı.
- Claude yerine **sahte Anthropic sunucusu** (127.0.0.1:8765, `ANTHROPIC_BASE_URL`) kullanıldı: hiçbir veri dış ağa gitmedi, **gerçek Claude çağrısı yok, maliyet 0**.
- Araçlar: `D_olcum.py` (yük, eşzamanlılık), `D_dayaniklilik.py` (sahte Claude, DB kilidi, Redis, kilit). Ham sonuçlar `D_ozet.json`, `D_dayaniklilik.json`.

## Bulunan ve düzeltilen 3 hata

| # | Deney | Düzeltme öncesi | Düzeltme sonrası |
|---|---|---|---|
| 1 | Akış ortasında Claude bağlantısı koptu | Kesik yanıt tam yanıt gibi gösterildi, uyarı yok (SDK hata vermedi, `stop_reason` boştu) | "Yanıt bağlantı hatası nedeniyle kesildi" notu ekleniyor |
| 2 | Claude hiç yanıt vermedi (askıda) | 271 sn sonra liste formatı (3 deneme × 90 sn; nginx sınırı 300 sn) | 180,6 sn (1 yeniden deneme, bağlantı sınırı 10 sn) |
| 3 | SQLite dosyası kilitli | `/health` 35 sn sonra **200** ve yanıltıcı "veri_yok" | `/health` 7,2 sn'de **503** "db_erisilemiyor"; kilit kalkınca anında 200 |

Kodlar: `app/rag.py` (`BAGLANTI_KOPTU_NOTU`, `CLAUDE_MAX_RETRIES`, `_claude_zaman_asimi`), `app/main.py` (`health_check` gerçek tablo okur). Test: 761 → 766 geçti (1 atlandı), flake8 hata sınıfları 0. Yeni testler: akış kopması (4), kilitli SQLite'ta hızlı 503 (1).

## Diğer ölçümler

| Deney | Sonuç |
|---|---|
| Sahte Claude 500 / 529 | Kullanıcıya liste formatı, 2 upstream isteği, 1,6 sn / 0,6 sn; hata metni sızmıyor |
| 5 eşzamanlı `/api/sor/akis` (rıza kapalı) | Hepsi 200, ilk parça 0,4–0,5 sn, toplam 0,5 sn |
| 5 eşzamanlı `/api/eslesme` (yetkili) | Hepsi 200, duvar süresi 0,13 sn |
| 30 sn × 5 iş parçacığı, 17.507 istek | `/health`: 5.836 istek hepsi 200, p50 11 ms, p95 27 ms, en yavaş 65 ms |
| Herkese açık hesap uçları (IP sınırı 30/dk) | Sınırdan sonra 429 (5.821 + 5.822 istek), p95 20 ms; sınır çalışıyor |
| Ölü `REDIS_URL` | Açılışta uyarı günlüğü, süreç içi sayaca düşüş, `/health` "surec_ici"; giriş sınırı çalışıyor (10 denemeden sonra 429) |
| Kilitli DB'de okuma/yazma | 7 sn sonra düz metin 500 "Internal Server Error" (JSON değil); kilit kalkınca anında normal |

## Denenemeyenler ve açık riskler
- **Gerçek modelle ilk parça / toplam süre (10 ölçüm): yapılmadı.** Anthropic kredisi bitti ve ücretli çağrı onayı yok. Eldeki veriler: Denetim 1'de ≈51 sn/yanıt, Aşama C'de 3 gerçek çağrı 26–39 sn (akışsız). Akışta ilk parça süresi **ölçülmedi**.
- **`--workers 2` zamanlayıcı tek sefer kanıtı: Windows'ta yok.** Windows'ta `fcntl` olmadığı için iki gerçek süreç de kilidi aldı (`True`, `True`); bu beklenen davranış (tek süreç varsayımı). `flock` yolunu yalnızca birim testi doğruluyor (`test_scheduler_kilidi`). Docker ve WSL yok, Linux'ta gerçek iki işçili kanıt **alınamadı**. Üretimde (Linux) çalıştırmadan önce doğrulanmalı.
- **Redis'in çalışırken düşmesi** gerçek Redis olmadan denenmedi; birim test `test_redis_erisilemezse_acik_kalir` "açık kal" davranışını doğruluyor.
- **DB kilidi altında okuma/yazma** düz metin 500 döner; kullanıcı mesajı JSON değil. Kısa kilitler için sorun değil, uzun yazan işlem (scraper) ile aynı SQLite dosyası paylaşılıyorsa PostgreSQL önerilir.
- Çalışan geliştirme sunucusu (:8000) bu düzeltmelerden önce başlatılmış; yeni kodu görmek için yeniden başlatılmalı.
