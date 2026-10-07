# Denetim 2 / Aşama I — başvuru belgeleri ve başvuru yeri (2026-10-08)

Amaç: Kullanıcı teşviki bulduktan sonra "hangi belgeleri hazırlayayım, nereye başvurayım" sorusunun yanıtı kartta
görünsün. Bu, evrak hazırlama desteğinin (kontrol listesi, taslak) ön koşulu.

## Seçim

12 persona × ilk 12 eşleşmede 49 farklı aktif program görünüyor. Bunların 34'ünde belge, başvuru yeri veya şart
alanı boştu (`I_aday_listesi.json`). En sık görünenler 9903 yatırım teşvikleri (Yerel Kalkınma Hamlesi 10 personada
1. sıra), KOSGEB Yapay Zekâ Kredisi ve KGF paketleri.

## Yöntem

Kaynak sayfalar Chrome'da salt okunur açıldı (hesapta işlem yok). Yalnızca sayfada görülen bilgi alındı;
değerlendirme, izleme ve ödeme aşaması formları (Teknik İnceleme, Kurul, Dönemsel İzleme, Sonuç Raporu, Ödeme Talep)
listeye girmedi. Düzeltme betiği yalnızca boş alanı doldurur: `scripts/fix_veri_2026_10_08_belgeler_tur9.py`
(dry-run varsayılan, idempotent, `--self-test` 7/7).

## Bulgular

| Kurum | Kayıt | Kaynakta bulunan |
|---|---|---|
| KOSGEB | 2, 9, 7, 5 | Sayfanın "Başvuru Formları ve Diğer Ekler" bölümü: başvuru formu, taahhütname, kontrol/hesaplama tablosu. Yapay Zekâ Kredisi'nde bankadan kesin teminat mektubu zorunlu (SSS). Küresel Rekabetçilik başvurusu KOBİ Bilgi Sistemi (KBS). |
| TÜBİTAK | 75, 39, 49, 25, 55, 48 | Başvurular PRODİS (eteydeb.tubitak.gov.tr); 1505 ve 1509 yıl boyunca açık. Formlar: Proje Öneri Bilgileri (AGY10x), Ar-Ge Yardımı İstek Formu (AGY3xx), BİGG'de AGY112 İş Planı ve Tahmini Maliyet Formları, 1707'de müşteri–tedarikçi işbirliği sözleşmesi. |
| Sanayi ve Teknoloji Bak. | 177–181 | 2 Temmuz 2018'den beri tüm teşvik belgesi başvuruları E-TUYS'te. Önce yetkilendirme: Dilekçe, Taahhütname, Kullanıcı Yetkilendirme Formu KEP ile Genel Müdürlüğe. |
| KGF | 16 paket | KGF belge listesi yayımlamıyor. Portföy Garanti Sistemi'nde KOBİ bankaya başvuruyor, banka kefalet talebini KGF'ye iletiyor ([süreç](https://www.kgf.com.tr/index.php/tr/kefalet-isleyisi/surec)). Paket sayfalarından kredi veren bankalar, kefalet başvuru ücreti ve pakete özgü şartlar alındı. KOSGEB destekli paketlerde (81, 107, 125) ilgili KOSGEB programının onayı ön koşul. TÜBİTAK Transfer Ödemeleri (152) doğrudan KGF'ye, 250 TL başvuru ücretiyle. |
| Tarım | 76 | HAYGEM duyurusu: talimat, iş takvimi ve başvuru dilekçesi örnekleri. |

## Bilerek boş bırakılanlar

- **KOSGEB İstihdamı Koruma (7) ve YÖNDE (5) başvuru yeri:** Sayfa kanalı yazmıyor (YÖNDE'deki KBS ifadesi yalnızca hizmet sağlayıcılar için).
- **Organik (77) ve Sera (79) belgeleri:** Kaynak 2026 birim fiyat tablosu; belge listesi içermiyor.
- **9903 programına özel belge listesi:** Uygulama tebliği metni taranmadı. Kayıtta yalnızca E-TUYS yetkilendirme belgeleri ve "ayrıntı E-TUYS kılavuzlarında" notu var.

## Etki (uygulandı 2026-10-08, yedek `tesvikler_oncesi_tur9.db.bak`; ölçüm sonrası sayım)

| Aktif kayıtlarda dolu | Önce | Sonra |
|---|---|---|
| Gerekli belgeler | 17 | 49 |
| Başvuru yeri | 27 | 49 |
| Başvuru şartları | 75 | 78 |

Personaların ilk 12 eşleşmesinde belge listesi olmayan program 34'ten 2'ye iner (77, 79).
