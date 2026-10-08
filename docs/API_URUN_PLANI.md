# Teşvik verisi ve uygunluk motoru — B2B API ürün planı (taslak, 2026-10-08)

Durum: **plan; kod yazılmadı.** Uygulama onaydan sonra; aşağıdaki "Uygulama planı" dosya listesi ve sırasıyla.

## 1. Ne satıyoruz
Model değil, **kaynaklı veri + deterministik uygunluk motoru**. Her yanıt kaynak adresi ve doğrulama tarihi taşır.
LLM yok: yanıtlar tekrarlanabilir, ücretsiz üretilir, profil yurt dışına çıkmaz.

| Uç nokta (v1) | Girdi | Çıktı | Mevcut karşılığı |
|---|---|---|---|
| `POST /v1/eslesme` | profil (sektör, il, NACE, çalışan, ciro, şirket türü, hedefler, kuruluş tarihi, isteğe bağlı ihracat USD) | sıralı programlar: skor, gerekçe, eksik kriterler, engel nedeni, çağrı | `matching.esles` (transient profil) |
| `POST /v1/uygunluk/{program_id}` | profil | uygun / kapalı + neden + hazırlık adımları | `uygunluk_engeli`, `hazirlik.program_adimlari` |
| `POST /v1/hazirlik` | profil | yol haritası: şirketleşme karşı-olgusu, ön şartlar | `hazirlik.yol_haritasi` |
| `GET /v1/cagrilar?gun=` | — | açık/yaklaşan çağrılar, firmanın son günü (ön kayıt) | `cagrilar` |
| `GET /v1/programlar/{id}` | — | şartlar, belgeler, başvuru yeri/süresi, tutar formülü, kaynak, doğrulama tarihi | `basvuru_listesi._yanit` |
| `POST /v1/eihracat/hesap` | 5986 giderleri + durum | şimdi/hazırlıkla/teyitle tutar, aylık bekleme | `eticaret_destek_hesaplayici` |
| `POST /v1/taslak/{program_id}` | profil | şablon başvuru ön taslağı (Markdown) | `sablon_taslak.uret` |

## 2. Kime
1. **Mali müşavir / ön muhasebe yazılımları** (müşteri portföyünde toplu uygunluk taraması) — en büyük dağıtım.
2. **E-ticaret altyapıları** (İKAS gibi): satıcıya e-ihracat geri ödemesi ve hazırlık adımları.
3. **Bankalar / KGF kanalı:** kredi başvurusunda uygun kefalet paketleri ve KOSGEB bağlantılı paketler.
4. **ERP / KOBİ portalları, ihracatçı birlikleri, kalkınma ajansları** (ikincil).

## 3. Teknik tasarım
- **Durumsuz:** profil istek gövdesinde gelir, **saklanmaz**; yalnız ölçüm için müşteri kimliği, uç nokta, zaman,
  yanıt kodu, süre tutulur. KVKK'da biz veri işleyen konumunda kalırız ve saklama yükü yoktur; DPA (veri işleme
  sözleşmesi) şablonu hazırlanır.
- **Kimlik doğrulama:** müşteri başına API anahtarı (`ta_live_…`, yalnız SHA-256 özeti saklanır), kapsam listesi
  (`eslesme`, `cagrilar`, `taslak`…), anahtar döndürme ve iptali. Mevcut kullanıcı JWT'sinden ayrı bağımlılık.
- **Sürüm:** `/v1` öneki; yanıt şeması pydantic modelleriyle sabit, OpenAPI dokümanı otomatik.
- **Hız sınırı ve kota:** mevcut `app/rate_limit.py` (Redis destekli) anahtar başına dakikalık sınır + aylık kota.
- **Ölçüm/faturalama:** `api_kullanim` tablosu (anahtar, uç nokta, gün, sayı); aylık özet uç noktası; Stripe metered
  billing ya da fatura (B2B'de yıllık sözleşme daha olası).
- **Veri tazeliği yanıtta:** her program için `kaynak_url`, `dogrulama_tarihi`, `durum_notu` özeti; KGF izleme ve
  veri turları sürdükçe güven artar.

## 4. Fiyat hipotezi (doğrulanacak)
Rakam koymadan önce 5 aday müşteriyle görüşme. Hipotezler: (a) çağrı başına kademeli fiyat, (b) müşteri portföyü
büyüklüğüne göre yıllık lisans (mali müşavir yazılımında "aktif mükellef" başına), (c) ücretsiz deneme kotası.
Maliyetimiz neredeyse sıfır (LLM yok); fiyat değer üzerinden (ör. e-ihracat hesabında geri alınabilir tutar).

## 5. Hukuki ve veri
- Kayıtlar kamu kurumlarının yayımladığı bilgiden **yapılandırılmış özet + kaynak bağlantısı**; kurum metinlerinin
  birebir toplu yeniden satışı yerine alan bazlı veri ve bağlantı verilir.
- Sorumluluk reddi: "ön değerlendirme; kesin uygunluk kurumca belirlenir" her yanıtta.
- KVKK: durumsuz işleme, DPA, yurt içinde barındırma.

## 6. Ölçütler ve vazgeçme (kill criteria)
- 90 günde en az 2 ücretli pilot (biri mali müşavir yazılımı) yoksa API ürününe yatırım durur, web/İKAS odaklanır.
- Pilotta yanlış uygunluk şikâyeti oranı persona ölçüm setiyle izlenir; doğruluk regresyonu sürüm engelidir.

## 7. Uygulama planı (onay sonrası)
| Sıra | Dosya | İş |
|---|---|---|
| 1 | `app/models.py` + göç | `api_anahtarlari` (org, özet, kapsamlar, durum), `api_kullanim` (gün bazlı sayaç) |
| 2 | `app/api_anahtar.py` | anahtar üretme/özetleme/doğrulama bağımlılığı, kapsam denetimi, kota |
| 3 | `app/api_v1.py` | 7 uç nokta (yukarıdaki tablo), transient profil şeması, sabit yanıt modelleri |
| 4 | `app/main.py` | router + panelde anahtar yönetimi uçları (`/api/api-anahtarlari`) |
| 5 | `tests/test_api_v1.py` | kimlik/kapsam/kota, durumsuzluk (profil DB'ye yazılmaz), yanıt şeması, persona eşitliği |
| 6 | `docs/API.md` | müşteri dokümanı + örnek istekler |

Risk: v1 yanıt şeması bir kez yayınlanınca değiştirilemez; persona ölçümünün API üzerinden de koşması (web ile aynı
sonuç) kabul ölçütü.
